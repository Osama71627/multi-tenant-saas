# Phase 11 Report — Notifications

**التاريخ:** 2026-08-23 (محدَّث — جولة REQUEST CHANGES الثانية)
**الحالة:** ✅ **مُعتمَدة جزئيًا سابقًا، الآن مكتملة** بعد جولة مراجعة ثانية طبَّقت تصحيحًا إلزاميًا لصحة الاسترداد (recovery correctness) + إثبات صريح لعزل tenant الخاص بعامل Celery — **699/699** اختبار ناجح فعليًا ضد PostgreSQL حقيقي (كانت 694 في نهاية التنفيذ الأول؛ +5 في جولة المراجعة الثانية)، 3 تشغيلات متتالية مستقرة، تغطية **98%** إجمالاً (**100%** على كل ملفات `apps.notifications` بلا استثناء)، كل بوّابات الجودة خضراء.

---

## 0.B جولة المراجعة الثانية (REQUEST CHANGES) — البندان، مُغلَقان

### 0.B.1 فجوة صحة الاسترداد: lookback لم يعد حدًّا للصحة (correctness cutoff)

**المشكلة المُكتشَفة فعليًا كما وصفتَها**: `recover_unprocessed_domain_events` كانت تعتمد حصريًا على `EventLog.created_at >= now() - NOTIFICATION_RECOVERY_LOOKBACK_HOURS` كشرط أهلية. حدث `order.confirmed` مُلتزَم فعليًا لكن لم يُرسَل له أي `on_commit` (انهيار العملية بين الالتزام والنشر) — إن ظلّت البنية التحتية معطَّلة أطول من نافذة الـlookback المُهيَّأة، يخرج الحدث من النافذة **ويُفقَد نهائيًا رغم عدم وجود `NotificationDispatch` له إطلاقًا أبدًا**. هذا ينتهك صراحة القاعدة المعتمَدة: "لا يجوز أن يُفقَد حدث domain مُلتزَم-وصالح-للإشعار نهائيًا لمجرّد انهيار العملية بين التزام DB ونشر Celery".

**الإصلاح** (`apps/notifications/tasks.py::recover_unprocessed_domain_events`، أُعيدت كتابتها بالكامل): الشكل الجديد `EventLog` (أنواع أحداث معروفة) `WHERE NOT EXISTS NotificationDispatch نهائي (event=<event>)` — العمر لا دور له في الأهلية إطلاقًا الآن. `EventLog` بقيت تمامًا كما كانت (سجلّ دائم غير قابل للتعديل، بلا عمود حالة/قفل جديد) — قراءة فقط هنا. `NotificationDispatch` تبقى المكان الوحيد الذي تعيش فيه حالة التسليم، كما هو مُعتمَد.

**قيد RLS حقيقي وُوجِه أثناء التنفيذ**: لا يمكن عمل anti-join عالمي واحد عبر كل المتاجر دفعة واحدة تحت RLS — الـGUC (`app.current_store_id`) قيمة scalar واحدة لكل اتصال، فلا يمكنها مطابقة أكثر من متجر واحد في نفس اللحظة؛ استعلام `NOT EXISTS` بلا سياق tenant صحيح يجعل **كل** صف غير مرئي لـ`app_user` (فشل مغلَق)، فيصبح الشرط "صحيح دائمًا" بلا معنى فعلي. **لم يُستخدَم `app_migrator`/BYPASSRLS لحل هذا** كما طلبتَ صراحة — الحل الفعلي: اكتشاف المتاجر المرشَّحة عبر `EventLog` (بلا RLS أصلًا، إعفاء موثَّق منذ Phase 1) هو استعلام آمن عابر للمستأجرين؛ ثم **لكل متجر على حدة**، يُنشَأ سياق tenant حقيقي (طبقة Python + طبقة RLS معًا)، ويُنفَّذ anti-join مُفهرَس ضد `NotificationDispatch` **ضمن ذلك السياق تحديدًا** — صحيح تمامًا لأن الـGUC يطابق المتجر الصحيح فعليًا.

**الترتيب/الحدود المطلوبة** — كلها مُطبَّقة حرفيًا:
- **ترتيب حتمي**: `order_by("created_at")` تصاعديًا لكل متجر.
- **حجم دفعة محدود**: `NOTIFICATION_RECOVERY_BATCH_SIZE_PER_STORE` (افتراضي 200) — متجر بتراكم أكبر من الحد يُكمَّل عبر عدّة تشغيلات متتالية، لا يُجوَّع أبدًا (الأحداث المُنجَزة فعليًا تخرج من الاستعلام تلقائيًا في المرة القادمة).
- **مقاومة فشل جزئي**: فشل استعلام اكتشاف متجر واحد (مثلًا عطل DB عابر) **لا يُوقِف** بقية المتاجر — يُلتقَط ويُسجَّل (`test_recovery_sweep_survives_one_stores_discovery_query_failing`، جديد).
- **معالجة idempotent**: بلا تغيير — نفس `process_committed_event` المُعتمَدة أصلًا.

**`NOTIFICATION_RECOVERY_LOOKBACK_HOURS`**: أُبقيَ عليه كما طلبتَ ("قد يبقى كتحسين أداء") لكن **أُعيد تعريف دوره صراحة**: لم يعد يُستخدَم كشرط WHERE للأهلية إطلاقًا — الآن يُستخدَم فقط لتسجيل `logger.warning` عند العثور على حدث أقدم من هذه النافذة (إشارة تشغيلية لِـoperator، لا حدّ صحّة).

**3 اختبارات ارتداد جديدة مطلوبة** (`apps/notifications/tests/test_recovery_lookback.py`)، كلها بإجبار `created_at` على قيمة قديمة فعليًا عبر `.update()` مباشرة بعد الإنشاء (يتجاوز `auto_now_add`، الطريقة الوحيدة لمحاكاة "حدث ظلّ عالقًا لفترة طويلة جدًا" دون انتظار فعلي):
1. `test_an_old_never_dispatched_event_is_still_recovered` — حدث أقدم من الـlookback العادي بلا `NotificationDispatch` ما زال قابلًا للاسترداد فعليًا (بريد حقيقي في outbox).
2. `test_an_old_event_with_a_terminal_dispatch_is_excluded_not_just_a_no_op` — حدث قديم له بالفعل `NotificationDispatch` بحالة `sent` ← **`processed == 0`** لهذا المتجر (إثبات أقوى من "no-op عند إعادة المعالجة": الحدث **مُستبعَد بالكامل** من الاستعلام، لا مجرَّد مُعاد معالجته بلا أثر).
3. `test_repeated_recovery_of_an_old_orphan_never_creates_a_second_dispatch` — 3 تشغيلات متتالية لحدث يتيم قديم ← تشغيل واحد فقط يُنتج dispatch (`processed >= 1` ثم `0` و`0`)، بريد واحد فقط عبر الثلاثة.

### 0.B.2 عامل Celery يُنشئ سياق tenant الخاص به بشكل مستقل — إثبات صريح

**التحقّق الفعلي**: قراءة `apps/notifications/tasks.py::_process_one_event` (المُستخدَمة من كلا المسارين، السريع والاسترداد) تؤكِّد أنها **دائمًا** تُنشئ `tenant_context(TenantContext(store_id=event.store_id))` + `apply_tenant_context_to_db(event.store_id)` مُشتقَّين من `EventLog.store_id` الدائم — **ليس** من أي حالة موروثة (لا HTTP request، لا GUC سابق). هذا هو التصميم الفعلي منذ التنفيذ الأول، لم يتغيَّر.

**لم يُوجَد أي bug إنتاجي** — طبَّقتُ ما طلبتَه حرفيًا: كتبتُ اختبار ارتداد صريح (`apps/notifications/tests/test_worker_tenant_isolation.py`) يبني Store A / Order A / حدث `EventLog` مُلتزَم حقيقي بلا أي `NotificationDispatch`، **يُثبِت صراحة عدم وجود أي سياق tenant نشط** (كلا الطبقتين: `get_current_store_id() is None` على مستوى Python، **و** `current_setting('app.current_store_id', true) == ''` مباشرة على مستوى اتصال PostgreSQL) قبل استدعاء المهمة، ثم يستدعي **بالضبط** نفس المسار الذي يستخدمه عامل Celery حقيقي: `config.celery.app.tasks["...process_domain_event"].apply_async(kwargs=...)` — نفس الاستدعاء الحرفي الذي تستخدمه `apps.core.events.emit_domain_event` نفسها، **وليس** استدعاء دالة Python مباشرًا لجسم المهمة. **نجح من أول تشغيل** — يُثبِت أن `CELERY_TASK_ALWAYS_EAGER` (بيئة الاختبار) لا يُخفي أي اعتماد خفي على GUC موروث من طلب HTTP: المهمة تشتق سياقها بالكامل من `EventLog.store_id` الدائم، تُنشئ `NotificationDispatch` الصحيح لـStore A، تُصيِّر من Order A، وتُسلِّم فعليًا إلى `Order A.email` (مُثبَت عبر `django.core.mail.outbox`). **لم يُستخدَم `app_migrator`/BYPASSRLS** — لم يكن هناك حاجة، لا مشكلة وُجدت.

`process_domain_event` في `apps/notifications/tasks.py` أُضيف لها docstring صريح يوثِّق هذه الآلية والاختبار المرتبط بها.

---

## 0. مسار الاعتماد

المقترح المعماري قُدِّم مع نقطتي قرار (آلية إطلاق Domain Event، ملكية `NotificationTemplate`) — **رُفِض** المقترح الأول (Django Signal + `transaction.on_commit()`) صراحة: "الـ Signals ممنوعة في المسارات الحرجة" (`docs/ARCHITECTURE.md` سطر 107) و"signal نفسها hidden orchestration داخل مسار Order حرج". اعتُمِد بدلًا منه **Option C** إلزاميًا: Domain Event صريح + سجلّ `EventLog` دائم + تسليم غير متزامن + مسح استرداد (recovery sweep) — موثَّق بـ22 قسمًا تفصيليًا، كلها مُطبَّقة حرفيًا أدناه. لا إعادة فتح لأي قرار من الاثنين المُعتمَدين (رفض الـSignals، `NotificationTemplate` عالمية).

---

## 1. المطابقة الدقيقة مع docs/ARCHITECTURE.md

| البند في الوثيقة | التطبيق الفعلي |
|---|---|
| سطر 107: "الـ Signals ممنوعة في المسارات الحرجة" | **لا Django Signal واحدة** في كامل Phase 11 — `apps.orders.services.confirm_order` يستدعي `apps.core.events.emit_domain_event` صراحة، سطرًا عاديًا داخل نفس المعاملة، لا `post_save`/`pre_save`/أي receiver |
| سطر 108: "كل عملية كتابة تُصدر Domain Event يُسجَّل في core.EventLog ويُرسل للـ Celery عند الحاجة" | `emit_domain_event` تكتب صفّ `EventLog` داخل معاملة المستدعي نفسها، ثم `transaction.on_commit()` يُسجِّل مهمة Celery — حرفيًا نفس الجملتين |
| سطر 247: الاتصال العكسي (domain أدنى → أعلى) يتم عبر Domain Events فقط | `apps.orders` **لا يستورد** `apps.notifications` إطلاقًا — الاتصال بالكامل عبر اسم نصّي (`settings.DOMAIN_EVENT_CONSUMER_TASKS`)، لا استيراد Python |
| سطر 242/244: `notifications` أعلى الطبقات، تحت `orders/payments/...` مباشرة | `apps.notifications` تستورد `apps.orders`/`apps.core` (اتجاه مسموح)؛ لا تطبيق آخر يستورد `apps.notifications` — مفروض بنيويًا (§9) |
| سطر 791 (جدول Roadmap): "Phase 11 — Notifications — قوالب + بريد + قنوات — بريد تأكيد الطلب يصل" | DoD الحرفي مُثبَت بـ`test_e2e_order_confirmation_delivery.py` عبر `django.core.mail.outbox` — ليس مجرد استدعاء `enqueue()` (§7) |

---

## 2. تطبيق Domain Event (Option C) خطوة بخطوة

**`apps/core/events.py`** (جديد، عام، لا يستورد أي تطبيق domain):
```python
def emit_domain_event(*, event_type, store_id, aggregate_type, aggregate_id, payload=None) -> EventLog:
    event = EventLog.objects.create(store_id=store_id, event_type=event_type,
        payload={"aggregate_type": aggregate_type, "aggregate_id": str(aggregate_id), **(payload or {})})
    for task_name in settings.DOMAIN_EVENT_CONSUMER_TASKS.get(event_type, []):
        def _enqueue(name=task_name, event_id=event.id):
            celery_app.tasks[name].apply_async(kwargs={"event_id": str(event_id)})
        transaction.on_commit(_enqueue)
    return event
```
- **الاستدعاء الوحيد المُصرَّح به**: `apps.orders.services.confirm_order` — السطر الأخير قبل `return locked`، داخل نفس معاملة تغيير حالة Order (§4 من المراجعة). **لا** استدعاء آخر من أي webhook/endpoint/caller — كلها تصل لـ`confirm_order` أولًا (مُثبَت: نقطة انتقال واحدة موثوقة → حدث domain واحد موثوق).
- **الحمولة (payload)**: `{aggregate_type: "order", aggregate_id, order_number}` فقط — معرّفات/سياق تدقيق، **لا** لقطة مالية ثانية (لا `total_amount`، لا `email`) — Order يبقى المصدر الوحيد الموثوق، القارئ اللاحق يعيد قراءته طازجًا.
- **التوقيت (§5)**: الكتابة والجدولة تحدثان **داخل** معاملة `confirm_order` نفسها؛ الإرسال الفعلي يحدث **بعد** الالتزام (`on_commit`) — لا بريد يُرسَل من داخل معاملة، لا قفل PostgreSQL محجوز أثناء SMTP. معاملة يُعاد التراجع عنها (rollback) بعد `confirm_order` ← لا `EventLog` محفوظ ولا محاولة إرسال (`test_rolled_back_order_confirmation_commits_no_event_and_no_dispatch`).

---

## 3. فجوة ما-بعد-الالتزام (§3 من المراجعة) — الحل الفعلي

السيناريو المطلوب: التزام DB ينجح → العملية تنهار قبل تشغيل `on_commit` → لا بريد يُجدوَل أبدًا رغم أن الطلب مؤكَّد فعليًا.

**الحل**: `apps/notifications/tasks.py::recover_unprocessed_domain_events` — مسح Celery-Beat دوري (`NOTIFICATION_RECOVERY_LOOKBACK_HOURS`، نافذة زمنية مضبوطة) يفحص `core.EventLog` (**ليس** جدول outbox منفصل — `EventLog` نفسه هو السجلّ الدائم فعلًا، حرفيًا سطر 108) لأنواع الأحداث المعروفة، ويُعيد تشغيل `process_committed_event` — **no-op آمن تمامًا** لأي حدث سبق ومُعالَج بنجاح (idempotent بالبناء، §11). `EventLog` لم يتحوّل إلى طابور مهام قابل للتعديل — لا حالة "معالجة" تُكتَب عليه، حالة التسليم بالكامل على `NotificationDispatch` (كما طلبتَ حرفيًا في §3 و§11).

**مُثبَت مباشرة** (`test_recovery.py`): محاكاة الفجوة بكتابة `EventLog` عبر `confirm_order` مباشرة بدون التقاط `on_commit` (بالضبط ما يبقى فعليًا على القرص بعد انهيار حقيقي) ← `recover_unprocessed_domain_events` يجد الحدث ويُنتج `NotificationDispatch` بحالة `sent` وبريدًا فعليًا في outbox. تشغيل ثانٍ للمسح بعد إرسال ناجح ← لا صفّ ثانٍ، لا بريد ثانٍ (`test_recovery_sweep_is_a_no_op_for_an_already_sent_dispatch`).

---

## 4. NotificationTemplate — عالمية، نفس نمط Plan (Phase 10)

نفس القرار المُعتمَد لجداول Plan حرفيًا: `BaseModel`/`TimeStampedModel` (لا `store_id`)، RLS بسياسة `SELECT` مفتوحة فقط (`global_readonly_policy_sql`، أُعيد استخدامها من Phase 10)، **لا** سياسة INSERT/UPDATE/DELETE لـ`app_user` — مُثبَت مباشرة (`test_template_rls.py`، 5 اختبارات): `app_user` يقرأ، INSERT يرفع استثناء RLS، UPDATE/DELETE يُصيبان صفر صفوف رغم وجود GRANT جدولي فعلي (`has_table_privilege` = True، الكتابة تُرفَض رغم ذلك)، `relrowsecurity` مفعَّلة فعليًا.

**الكتابة فقط عبر `app_migrator`** — القاعدة نفسها التي فرضتها مراجعة Phase 10 (§0.A.1 هناك): `apps/notifications/management/commands/publish_notification_template.py` أمر إداري صريح، يرفض العمل (`CommandError`) إن لم يُمرَّر `--database=migrator`. **لا** خدمة تطبيق تفتح صلاحية `migrator` — لا تكرار لخطأ Phase 10 الأول. القالب الوحيد المطلوب للـDoD (`order_confirmation`/`en`) مبذور عبر migration (`0002_seed_order_confirmation_template.py`)، يعمل تلقائيًا في كل بيئة عبر `migrate`.

---

## 5. أمان عرض القوالب (§8) — لا تنفيذ Jinja/Python عشوائي

`apps/notifications/rendering.py` تستخدم `string.Template.safe_substitute()` (مكتبة قياسية) عمدًا: بنية `$name` المسطّحة **لا تملك** أي صيغة وصول لخاصية/دالة/عنصر إطلاقًا — لا شيء يشبه `{{ order.customer.delete }}` موجود أصلًا لاستغلاله. سياق العرض (`build_order_confirmation_context`) قاموس نصوص مسطّح فقط (`order_number`, `order_email`, `order_total`, `store_name`) يُبنى صراحة من قِبَل الخدمة — لا نموذج (model instance) يُمرَّر للمُعالِج إطلاقًا. `safe_substitute` (لا `substitute`): مفتاح سياق غائب لا يرفع استثناء، placeholder بلا مفتاح مطابق يبقى نصًا حرفيًا — لا 500 من خطأ إملائي في قالب.

---

## 6. قناة الإرسال (§9، §10)

`apps/notifications/channels/base.py::NotificationChannel` (ABC صغيرة، `send(recipient, subject, body)`) + التطبيق الوحيد الفعلي `EmailChannel` (`send_mail` من Django — نفس الآلية التي يستخدمها `apps.accounts` أصلًا لتفعيل الحساب/استعادة كلمة المرور، §18). **لا** SMS/WhatsApp/Push — لم تُبنَ، الوثيقة تذكر "قنوات" لكن Phase 11 الفعلي بريد فقط، حسب الاعتماد الصريح. طابور Celery المستخدَم هو `"email"` الموجود أصلًا (`CELERY_TASK_ROUTES`)، لا طابور جديد.

فشل مزوّد البريد **معزول تمامًا** عن صحة Order/Payment/Inventory: `_process_one_event` (`tasks.py`) يلتقط أي استثناء ولا يُعيد رفعه أبدًا خارج المهمة — `test_transient_send_failure_never_touches_order_payment_or_inventory` يُثبِت أن `Order.status` يبقى `confirmed` بلا مساس حتى مع فشل SMTP محاكى.

---

## 7. الإثبات الفعلي المطلوب (§12 من المراجعة الأصلية، §19 بند 10) — لا ادّعاء "exactly-once" بلا دليل

`test_e2e_order_confirmation_delivery.py` — تدفّق storefront حقيقي عبر HTTP (سلة → checkout → عنوان/شحن → إكمال) → `confirm_order` الحقيقي → `captureOnCommitCallbacks` يُشغِّل `on_commit` فعليًا → **يُثبَت مباشرة أن `django.core.mail.outbox` يحتوي رسالة فعلية** بموضوع ومحتوى القالب المبذور الحقيقي (`f"Your order {number} is confirmed"`)، لا مجرد أن `apply_async` استُدعِيت.

**الدلالة المُصرَّح بها صراحة، بلا مبالغة**: هذا يضمن "استلام واحد محليًا موثَّق" (`NotificationDispatch` واحد، حالة `sent`) — وليس بالضرورة "تسليم SMTP خارجي مرة واحدة بالضبط". لا يوجد تكامل مزوّد بريد حقيقي في هذه المرحلة يوفّر idempotency على مستوى الشبكة، فلا ادّعاء بذلك. الدلالة الدقيقة: **at-least-once delivery مع قمع تكرار محلي (local duplicate suppression)** — إن أعاد Celery محاولة نفس الحدث بعد قبول SMTP للرسالة لكن قبل تسجيل النجاح محليًا، قد يصل بريدان فعليان رغم صفّ `NotificationDispatch` واحد نهائيًا.

---

## 8. Idempotency (§11)

`NotificationDispatch` — `UniqueConstraint(store, event, channel, notification_type)` (**ليس** `(store, event_type, target_email)` كما حذَّرت المراجعة — عدة Orders يمكن أن تتشارك بريدًا واحدًا). `process_committed_event` تستخدم `get_or_create` بهذا المفتاح؛ إن كانت الحالة القائمة terminal (`sent`/`failed`/`dead_letter`) ← no-op فوري.

**مُثبَت**: نفس الحدث يُعالَج 10 مرات متتالية ← صفّ `NotificationDispatch` واحد فقط، حالة `sent` (`test_same_event_processed_repeatedly_yields_one_logical_dispatch`). **تزامن حقيقي** (`test_dispatch_concurrency.py`، نفس نمط `psycopg`/threads المُثبَت في Phase 8/9/10): جلستا PostgreSQL منفصلتان فعليًا تحاولان INSERT لنفس مفتاح التفرّد في نفس اللحظة (حاجز `threading.Barrier`) ← واحدة `claimed`، الأخرى `duplicate` (`UniqueViolation` مُلتقَطة)، صفّ واحد نهائيًا في القاعدة.

**حدّ صريح موثَّق** (§20 من المراجعة): هذا يُثبِت قرار dispatch محلي واحد فقط — لا يُثبِت استحالة وصول بريدين خارجيين فعليًا عبر SMTP (§7 أعلاه).

---

## 9. Retry/Failure/DLQ (§13)

`_MAX_ATTEMPTS = 5` على `NotificationDispatch.attempts`:
- خطأ SMTP/شبكة عابر (أي `Exception` غير مصنَّفة أدناه) → `attempts += 1`، يبقى `pending` قابلًا لإعادة المحاولة عبر مسح الاسترداد، حتى الوصول لـ5 ← `dead_letter`.
- `PermanentSendError` (مستلم فارغ مثلًا) → `failed` فورًا، **لا** يُحتسَب كمحاولة قابلة لإعادة المحاولة.
- `TemplateNotConfiguredError` (فجوة إعداد، لا فشل عابر) → `failed` فورًا، بلا crash غير مُعالَج خارج المهمة (`test_missing_template_fails_the_dispatch_terminally_without_crashing_the_task`).

**تبسيط تصميمي مُصرَّح به صراحة** (لا ادّعاء زائف): `process_domain_event` (المسار السريع) **لا** يستخدم `retry`/`autoretry_for`/backoff الخاصة بـCelery — محاولة واحدة فقط، ثم يلتقط الفشل ويُسجِّله دون إعادة رفعه (لتجنّب حجز أي شيء داخل `on_commit` لمدة backoff، أو تسريب استثناء لمسار المستدعي الأصلي). **إعادة المحاولة الوحيدة الفعلية هي مسح الاسترداد الدوري** (فاصل ثابت، وليس exponential backoff لكل محاولة) — هذه محدودية حقيقية لهذه المرحلة، موثَّقة صراحة في docstring الوحدة، لا مخفيّة. **لا بنية DLQ حقيقية منفصلة موجودة** — `dead_letter` هي مجرد قيمة `status` قابلة للاستعلام عبر `NotificationDispatch`، لا طابور DLQ فعلي منفصل — لا ادّعاء بوجوده.

---

## 10. NotificationPreference (§14)

**لم يُبنَ** — لا مطلب فعلي ظهر يستدعيه. بريد تأكيد الطلب يبقى **إلزاميًا دائمًا** في هذه المرحلة (لا تفضيل عام يمكن أن يُسقِطه)، بالضبط كما طلبت المراجعة. لا معماريّة موافقة تسويقية للعميل بُنيت.

---

## 11. عزل tenant (§15)

`NotificationDispatch` — `TenantOwnedModel` قياسية، RLS كاملة (`standard_tenant_policy_sql`، نفس نمط Phase 8/9/10)، **بلا** أي استثناء نمط `EventLog`. مُسجَّلة في `apps/notifications/tests/isolation_factories.py` ومُضافة لمجموعة العزل العامة (`tests/test_tenant_isolation.py`).

`test_cross_tenant.py` — سيناريو حقيقي كامل: متجران مستقلان، كل منهما يُكمِل شراءً ببريد مختلف حقيقي (اكتُشِف أثناء كتابة هذا الاختبار أن مساعد الـcheckout المشترك يستخدم بريدًا موحَّدًا "shopper@example.com" لكل الاختبارات — أُضيف مساعد محلي بريد مخصَّص لكل متجر لجعل الاختبار ذا معنى فعليًا، §12 أدناه). يُثبَت: كل متجر يستلم بريده فقط (outbox)، ومتجر A **حتى عبر `.unscoped`** تحت سياق tenant الخاص به لا يرى صفّ dispatch متجر B — RLS الفعلي على مستوى DB، لا فلتر Python فقط.

---

## 12. أخطاء وُجدت وأُصلحت أثناء البناء

هذه المرحلة كشفت 4 أخطاء بنية تحتية حقيقية — كانت كامنة منذ مراحل سابقة (Phase 0/1) لكن لم تُكتشَف لأن أيًا من الأكواد السابقة لم يعتمد فعليًا على `on_commit`/tasks بالاسم قبل الآن:

1. **`Celery.send_task()` يتجاهل `CELERY_TASK_ALWAYS_EAGER`** — مصدر Celery نفسه يُصدر تحذير `AlwaysEagerIgnored` صراحة، يُرسِل دائمًا للـbroker الحقيقي. **الإصلاح**: `celery_app.tasks[name].apply_async(...)` (عبر سجلّ المهام نفسه) بدل `send_task`/`current_app.send_task`.
2. **`autodiscover_tasks()` كسولة (lazy) خارج عامل Celery حقيقي** — تُؤجِّل استيراد وحدات المهام الفعلية حتى إشارة `import_modules` الداخلية، التي لا تُطلَق أبدًا خارج bootstrap عامل حقيقي — سجلّ المهام كان **فارغًا فعليًا** لكل التطبيقات (بما فيها `apps.payments`/`apps.subscriptions` من مراحل سابقة) خارج عامل حقيقي طوال المشروع، بلا أن يُكتشَف لأن لا كود سابق بحث عن مهمة بالاسم عبر السجلّ. **الإصلاح**: `apps/core/apps.py::CoreConfig.ready()` يستدعي `celery_app.autodiscover_tasks(force=True)` بعد اكتمال سجلّ تطبيقات Django (استدعاؤها مباشرة في `config/celery.py` عند مستوى الوحدة يفشل بـ`AppRegistryNotReady` بسبب استيراد دائري توقيتي).
3. **`transaction.on_commit()` لا يُطلَق إطلاقًا تحت عزل اختبار pytest-django الافتراضي** — كل الاختبار يعمل داخل معاملة خارجية واحدة تُعاد للوراء (rollback) في النهاية، فلا التزام حقيقي يحدث أبدًا، فلا callback مُسجَّل عبر `on_commit` يُطلَق تلقائيًا مطلقًا — فجوة اختبار حقيقية غير مكتشفة سابقًا في كل المشروع (لا مرحلة سابقة اختبرت كودًا يعتمد على `on_commit`). **الإصلاح**: `django.test.TestCase.captureOnCommitCallbacks(execute=True)` (أداة Django الرسمية لهذا بالضبط) حول كل استدعاء `confirm_order` في اختبارات Phase 11.
4. **تكوين توجيه مهام Celery مكرَّر ومتعارض** — `config/celery.py` كان يحتوي `app.conf.task_routes = {...}` مكتوبًا مباشرة، **يُبطِل بصمت** ما حمّلته `config_from_object` من `CELERY_TASK_ROUTES` في settings — خطأ مصدر-حقيقة-مزدوَج موجود منذ Phase 0/1، غير مكتشَف سابقًا لأن القيم توافقت صدفة لـ`apps.payments`. **الإصلاح**: حُذِف الكتلة الثابتة، `CELERY_TASK_ROUTES` في settings أصبحت مصدر الحقيقة الوحيد.

خطأ اختبار إضافي (لا كود إنتاجي): مساعد `store_db_context` (من `apps.orders.tests.conftest`) يمسح GUC الـtenant دون شرط عند الخروج بدل استعادة قيمة سابقة — تداخل استدعاءين له كسر سياق البلوك الخارجي بصمت. أُصلِح بعدم تداخل الاستدعاءات إطلاقًا، وباكتشاف نمط ثانٍ أثناء كتابة اختبار "بريد المستلم من لقطة Order": مهمة Celery المُشغَّلة تزامنيًا داخل `captureOnCommitCallbacks` تمسح GUC عند خروجها بنفس الآلية — أي استعلام لاحق **داخل نفس بلوك `store_db_context` الذي استدعى `confirm_order`** يرى GUC فارغًا. الإصلاح المُتَّبع في كل الاختبارات المتأثرة: إغلاق البلوك بعد `confirm_order` مباشرة، فتح بلوك `store_db_context` **جديد** للاستعلامات اللاحقة.

خطأ اختبار ثالث (`test_cross_tenant.py`): مساعد الـcheckout المشترك يستخدم بريدًا ثابتًا واحدًا لكل الاختبارات — جعل التحقق الأول من عزل المستلمين صحيحًا صدفة (كلا المتجرين ينتجان نفس البريد، فالمقارنة تمرّ تافهًا). أُصلِح بمساعد محلي يقبل بريدًا مخصَّصًا لكل متجر.

لا bugs إنتاجية بقيت غير مُصلَحة أو غير موثَّقة.

---

## 13. تغطية DoD

| المتطلَّب | مُنفَذ؟ | الدليل |
|---|---|---|
| بريد تأكيد الطلب يصل فعليًا (سطر 791) | ✅ كامل | `test_e2e_order_confirmation_delivery.py` — outbox حقيقي، محتوى القالب الحقيقي |
| نقطة إطلاق واحدة موثوقة (`confirm_order`) | ✅ كامل | §2، مُثبَت أن كل الاستدعاءات الأخرى (webhook/COD/checkout) تصل لها أولًا |
| لا Signals في المسار الحرج | ✅ كامل | §1 |
| فجوة ما-بعد-الالتزام مُعالَجة | ✅ كامل | §3 |
| Idempotency حقيقية (منطقية + تزامن DB حقيقي) | ✅ كامل | §8 |
| عزل tenant كامل (RLS، ليس فلتر Python فقط) | ✅ كامل | §11 |
| المستلم من لقطة `Order.email`، لا مصدر آخر | ✅ كامل | `test_recipient_snapshot.py` — تعديل CheckoutSession حيًا قبل التأكيد لا يُغيِّر المستلم |
| localization: fallback واضح، لا crash صامت | ✅ كامل | `test_localization.py` — fallback للغة المنصة، خطأ تهيئة واضح عند غياب كامل |
| أمان عرض القوالب (لا تنفيذ عشوائي) | ✅ كامل | §5 |
| `NotificationTemplate` عالمية RLS (نفس نمط Plan) | ✅ كامل | §4 |

---

## 14. Technical debt مؤجَّل عمدًا (موثَّق، لا افتراض تلقائي بالتوسّع)

| البند | لماذا |
|---|---|
| `EventLog` غير مُستخدَم كتابيًا في أي خدمة من Phase 1-10 | مذكور صراحة كما طلبتَ (§21 من المراجعة): موجود كنموذج منذ Phase 1، لكن لم يُوصَّل لأي مسار كتابة حتى `order.confirmed` في Phase 11 — لا إعادة كتابة لكل الخدمات السابقة دفعة واحدة، توسّع مستقبلي منفصل إن ظهر مبرّر فعلي |
| SMS/WhatsApp/Push channels | لا تنفيذ فعلي مطلوب في Phase 11 — `NotificationChannel` ABC تبقى صغيرة، `EmailChannel` هو التطبيق الوحيد |
| قوالب مخصَّصة لكل متجر / محرِّر HTML | مؤجَّل صراحة (§7 من المراجعة) — DoD هو وصول بريد التأكيد، ليس بناء Email Builder |
| `NotificationPreference` | لم يُبنَ — لا مطلب فعلي ظهر (§10 أعلاه) |
| DLQ حقيقي منفصل | `dead_letter` قيمة status فقط، لا بنية طابور منفصلة — §9 |
| exactly-once تسليم SMTP خارجي | غير مُثبَت ولا مُدَّعى — الدلالة الموثَّقة هي at-least-once + قمع تكرار محلي (§7) |
| Celery retry/backoff لكل محاولة | مُستبدَل عمدًا بمسح استرداد بفاصل ثابت — §9 |

---

## 15. جميع الاختبارات ونتائجها

```
699 passed (3 تشغيلات متتالية مستقرة للمجموعة الكاملة، بعد جولة المراجعة الثانية)
```
`apps/notifications/tests/` — **42 اختبارًا** إجمالًا (37 من التنفيذ الأول + **5 جديدة** في جولة المراجعة الثانية)، كلها ضد PostgreSQL حقيقي:
- `test_domain_event_emission.py`: 2 — حدث واحد فعليًا عند الالتزام، لا شيء عند rollback
- `test_dispatch_idempotency.py`: 4 — 10 معالجات متكرِّرة → صفّ واحد، فشل عابر لا يمسّ Order/Payment/Inventory، خطأ دائم فوري، dead-letter بعد 5 محاولات
- `test_recovery.py`: 2 — محاكاة الفجوة + معالجتها، no-op على إرسال مكتمل
- **`test_recovery_lookback.py`: 3، جديد (القسم 0.B.1)** — حدث يتيم أقدم من الـlookback ما زال قابلًا للاسترداد، حدث قديم منتهٍ يُستبعَد من الاستعلام تمامًا (لا مجرَّد no-op)، 3 تشغيلات متتالية لحدث يتيم قديم ← dispatch واحد فقط
- **`test_worker_tenant_isolation.py`: 1، جديد (القسم 0.B.2)** — عامل Celery يشتق سياق tenant من `EventLog.store_id` وحده، بلا أي سياق موروث (مُثبَت على طبقتي Python وPostgreSQL معًا)، عبر `apply_async` الحقيقي لا استدعاء دالة مباشر
- `test_template_rls.py`: 5 — نفس نمط إثبات Plan RLS من Phase 10
- `test_cross_tenant.py`: 1 — عزل كامل بين متجرين، RLS فعلي لا فلتر Python
- `test_recipient_snapshot.py`: 1 — المستلم من لقطة Order.email فقط
- `test_localization.py`: 4 — fallback للغة المنصة، تفضيل تطابق دقيق، خطأ تهيئة واضح، لا crash عند غياب القالب
- `test_e2e_order_confirmation_delivery.py`: 1 — **إثبات DoD الفعلي**، outbox حقيقي
- `test_dispatch_concurrency.py`: 1 — تزامن DB حقيقي (psycopg/threads)، صفّ واحد نهائيًا
- `test_publish_notification_template_command.py`: 4 — رفض alias غير migrator، إنشاء، upsert، `--inactive`
- **`test_edge_cases.py`: 4** (كانت 3؛ +1 في جولة المراجعة الثانية) — event_id غير موجود، حدث بلا store_id، EmailChannel يرفض مستلمًا فارغًا، **فشل استعلام اكتشاف متجر واحد لا يُوقِف بقية المسح**
- `test_services_guards.py`: 3 — نوع حدث غير معنيّ، حمولة بلا aggregate_id، Order غير مرئي/محذوف

---

## 16. Coverage

```
98% إجمالاً (3605 عبارة، 58 غير مُغطاة — موروثة من مراحل سابقة، غير مرتبطة بـPhase 11)
apps/notifications/__init__.py                                          100%
apps/notifications/apps.py                                              100%
apps/notifications/channels/base.py                                     100%
apps/notifications/channels/email.py                                    100%
apps/notifications/management/commands/publish_notification_template.py 100%
apps/notifications/models.py                                            100%
apps/notifications/rendering.py                                         100%
apps/notifications/services.py                                          100%
apps/notifications/tasks.py                                             100% (أُعيدت كتابتها في جولة المراجعة الثانية، بلا فقدان تغطية)
```

---

## 17. Quality Gates

| البوّابة | النتيجة |
|---|---|
| ruff | ✅ نظيف |
| black | ✅ نظيف |
| mypy | ✅ نظيف (260 ملف مصدر، صفر أخطاء — خطأ جديد وُجِد وأُصلِح في جولة المراجعة الثانية: `store_id` غير مُضيَّق في حلقة `recover_unprocessed_domain_events` الجديدة، نفس نمط `_process_one_event`) |
| bandit | ✅ صفر مشاكل |
| import-linter | ✅ **11 عقدًا** (بلا تغيير في جولة المراجعة الثانية)، صفر مخالفات |
| makemigrations --check | ✅ لا تغييرات مفقودة (لا migration جديدة — `NOTIFICATION_RECOVERY_BATCH_SIZE_PER_STORE` إعداد بيئة فقط، لا حقل نموذج) |
| pytest | ✅ 699/699، تغطية 98%، 3 تشغيلات متتالية للمجموعة الكاملة |
| ضمان عزل قاعدة اختبار PostgreSQL | ✅ نشط طوال المرحلة، لم يُلمَس |

---

## 18. القرارات المعمارية الجديدة

| القرار | السبب |
|---|---|
| Domain Event صريح + `on_commit` + مسح استرداد (Option C)، لا Signals | رفض صريح لمقترح Signal الأول — hidden orchestration في مسار حرج غير مقبول |
| `celery_app.tasks[name].apply_async(...)` بدل `send_task`/`current_app` | خطآن حقيقيان مُكتشَفان (§12، البندان 1-2) — الطريقة الوحيدة التي تحترم `CELERY_TASK_ALWAYS_EAGER` وتحلّ لتطبيق Celery الصحيح |
| `NotificationDispatch` هي مصدر حالة التسليم، لا `EventLog` | كما طلبتَ حرفيًا (§3، §11 من المراجعة) — `EventLog` يبقى سجلّ حدث دائم، لا طابور مهام قابل للتعديل |
| مسح استرداد بفاصل ثابت، لا Celery retry/backoff لكل محاولة | تبسيط مُصرَّح به صراحة — تجنّب حجز أي شيء داخل `on_commit`، تجنّب تسريب استثناء retry-exhaustion لمسار Order الأصلي |
| `string.Template.safe_substitute()` بدل أي محرِّك Jinja | يمنع بنيويًا أي صيغة وصول خاصية/دالة — لا حاجة لـsandboxing إضافي |
| `NotificationTemplate` عالمية، RLS `SELECT`-only، كتابة عبر `app_migrator` فقط | نفس نمط Plan من Phase 10 حرفيًا — لا تكرار لخطأ Phase 10 الأول (لا خدمة تطبيق تفتح `migrator`) |
| **الاسترداد: anti-join لكل متجر ضد `NotificationDispatch` بدل `EventLog.created_at` كحدّ صحّة (§0.B.1، جولة المراجعة الثانية)** | fix إلزامي — lookback بمفرده يسمح بفقدان حدث يتيم قديم نهائيًا؛ RLS يمنع anti-join عالمي واحد (GUC scalar واحد لكل اتصال)، فالحل الصحيح الوحيد بلا bypass هو المسح لكل متجر ضمن سياقه الحقيقي |
| `NOTIFICATION_RECOVERY_LOOKBACK_HOURS` أصبح إشارة تشغيلية (log فقط)، لا حدّ WHERE | نفس القسم — "قد يبقى كتحسين أداء" لكن ليس "الحدّ الوحيد للصحّة" كما طلبتَ حرفيًا |

---

## المرحلة التالية

بانتظار موافقتك الصريحة قبل تحديد المرحلة التالية حسب خارطة الطريق.
