# Phase 10 Report — Subscriptions

**التاريخ:** 2026-08-22 (محدَّث 2026-08-23 — جولة REQUEST CHANGES)
**الحالة:** ✅ **مُعتمَدة ومُغلَقة نهائيًا** بعد جولة مراجعة (REQUEST CHANGES) طبَّقت تصحيحًا معماريًا إلزاميًا لحدود `app_migrator` + بوّابة `read_only` إلزامية على بدء دفعة جديدة — **657/657** اختبار ناجح فعليًا ضد PostgreSQL حقيقي (كانت 582 في نهاية Phase 9؛ +67 في التنفيذ الأول = 649؛ +8 في جولة المراجعة = 657)، 3 تشغيلات متتالية مستقرة، تغطية **98.26%** إجمالاً، كل بوّابات الجودة خضراء.

---

## 0.A جولة المراجعة (REQUEST CHANGES) — البندان، مُغلَقان

### 0.A.1 `app_migrator` لم يعد يُفتَح من أي مسار خدمة إنتاجي

التقرير الأول وثَّق أن `apps.subscriptions.services.publish_plan_version` كانت تكتب عبر alias `"migrator"` مباشرة من طبقة الخدمة — رُفِض هذا صراحة: `app_migrator` مخصَّص لِـmigrations/controlled setup فقط منذ Phase 1، وليس لـ"خدمة تطبيق تفتح صلاحية مميّزة عند الحاجة"، حتى لو كانت الوجهة جداول Plan العالمية المقصودة أصلًا كـ read-only لـ`app_user`.

**الإصلاح**: حُذِفت `publish_plan_version` بالكامل من `apps/subscriptions/services.py` (طبقة الخدمة التي يستدعيها كود التطبيق العادي). محلّها الآن **أمر إداري صريح** (`apps/subscriptions/management/commands/publish_plan_version.py`، نفس فئة `manage.py migrate` نفسها — إجراء يُشغِّله مشغِّل بشري يملك بيانات اعتماد `MIGRATOR_DATABASE_URL`، لا كود يخدم طلبات HTTP أبدًا). الأمر يرفض العمل صراحة (`CommandError`) إن لم يُمرَّر `--database=migrator`. `upgrade_subscription`/`schedule_downgrade` (تكتبان فقط على `Subscription`، جدول tenant-owned مسموح لـ`app_user`) بقيتا في `services.py` بلا تغيير — لم يكن فيهما أي مشكلة.

الحدود النهائية كما طلبتَ حرفيًا:
- `app_user` → قراءة فقط على بيانات Plan العالمية (بلا تغيير — كانت مضمونة أصلًا عبر RLS).
- `app_migrator` → migrations + seed/setup مضبوط فقط (الأمر الإداري الجديد ينضم لنفس هذه الفئة، وليس فوقها).
- Platform Admin مستقبلي → معمارية كتابة مخصَّصة، تُصمَّم عند وصول مرحلتها في خارطة الطريق — لم يُبنَ أي بديل مؤقَّت له هنا.

اختبارات RLS الموجودة (`test_plan_rls.py`) التي تُثبِت عجز `app_user` عن الكتابة على Plan **لم تُمَس** — أُعيد تشغيلها مباشرة (القسم "التحقق" أدناه) وما زالت 8/8 ناجحة. أُضيف اختبار جديد واحد (`test_command_refuses_to_run_against_the_default_alias`) يُثبِت أن الأمر نفسه يرفض العمل ضد alias غير migrator.

### 0.A.2 `POST storefront/payments/initiate` يرفض بدء دفعة جديدة على متجر `read_only`

تحقَّق فعليًا: **لم يكن هناك أي حارس** على هذا المسار قبل الإصلاح — `PaymentInitiateView` يرث من `StorefrontAPIView` (وليس `StoreScopedAPIView`)، والذي لا يمرّ أصلًا عبر `apps.stores.hooks.check_write_gates`. السيناريو الذي وصفتَه (Order موجود بالفعل `pending_payment` قبل أن يصبح المتجر `read_only`، ثم طلب `initiate`) كان سيمرّ بلا أي منع.

**الإصلاح**: `entitlements.require_active_store(store=store)` أُضيفت كأول سطر فعلي داخل `apps.payments.services.initiate_payment` — **قبل** مطالبة idempotency وقبل أي استدعاء شبكي، فلا يترك أي أثر جانبي عند الرفض (لا `PaymentIdempotencyKey` مُطالَب بها، لا `PaymentIntent`، لا استدعاء provider). `apps.payments.views.PaymentInitiateView` تُترجِم `StoreNotPurchasableError` إلى 402. `apps.payments` يستورد `apps.subscriptions.entitlements` مباشرة (اتجاه مسموح: payments فوق subscriptions في الطبقات أصلًا، بلا أي تعارض جديد).

**لم يُلمَس** أي من: `process_webhook`، `apply_payment_transition`، `reconcile_stuck_payment_intents`، `capture_manual_cod_payment` — كلها تُكمِل/تُعافِج `PaymentIntent` **موجودة بالفعل**، لا تبدأ شراءً جديدًا، بالضبط كما حدَّدتَ. اختبار مباشر (`test_read_only_store_does_not_block_webhook_processing_of_an_existing_intent`) يُثبِت أن webhook حقيقي على intent مُبتدَأ قبل `read_only` يُكمِل إلى `succeeded` بلا عائق.

**3 اختبارات جديدة** (`apps/payments/tests/test_read_only_gate.py`):
1. متجر `read_only` + Order `pending_payment` موجود ← `initiate` يُرفَض بـ402، **لا** `PaymentIntent`، **لا** `PaymentIdempotencyKey`، **لا** استدعاء provider (مُثبَت بـ`unittest.mock.patch` على `MockProvider.create_payment` + `assert_not_called()`)، Order يبقى `pending_payment` بلا تغيير.
2. متجر `active` عادي ← `initiate` يعمل بلا تأثر (201).
3. متجر يصبح `read_only` **بعد** بدء دفعة ناجحة سابقًا ← webhook لاحق على نفس الـintent يُكمِل بلا عائق (200، الحالة تنتقل إلى `succeeded`).

---

## 0. مسار الاعتماد

المقترح المعماري الكامل (16 نقطة) قُدِّم واعتُمِد مع تعديلات إلزامية مفصَّلة على 4 قرارات صعبة التراجع (RLS/ownership لجداول Plan، دلالات downgrade-below-usage، plan versioning علائقي بدل JSONB snapshot، حدود app boundary). كل تعديل مُطبَّق حرفيًا أدناه، بلا إعادة فتح لأي قرار من الـ~19 قرارًا المُقفَلة مسبقًا.

---

## 1. ما تم تنفيذه فعليًا

### apps.subscriptions (تطبيق جديد)

**النماذج العالمية** (`Plan`, `PlanVersion`, `PlanVersionFeature`, `PlanVersionQuota`) — `BaseModel`/`TimeStampedModel` مباشرة (لا `store_id`)، RLS مفعَّلة بسياسة `SELECT` مفتوحة فقط (`apps.tenancy.rls.global_readonly_policy_sql`، دالة جديدة عامة إلى جانب `standard_tenant_policy_sql`) — **لا** سياسة INSERT/UPDATE/DELETE لـ`app_user` إطلاقًا، فتُرفَض كل كتابة من التطبيق العادي حتى لو كان لديه GRANT جدولي (القسم 2). الكتابة فقط عبر `app_migrator` (migrations/fixtures/shell).

**النماذج المملوكة للمستأجر** (`Subscription`, `UsageRecord`, `Invoice`) — `TenantOwnedModel` قياسية، RLS كاملة، بلا أي استثناء "بيانات فوترة" (بخلاف سابقة `EventLog` المعفاة من RLS عمدًا — لم تُمدَّد لهذه الجداول كما طلبتَ صراحة).

**Plan versioning علائقي، لا JSONB** (تصحيحك الصريح على المقترح الأول): `PlanVersion` هي النسخة الثابتة (immutable) نفسها — لا حاجة لأي snapshot إضافي على `Subscription`. `apps.subscriptions.services.publish_plan_version` تُنشئ نسخة **جديدة** دائمًا (رقم تسلسلي متزايد، `UniqueConstraint` يمنع أكثر من نسخة `is_current=True` واحدة لكل خطة)، لا تُعدِّل نسخة قائمة أبدًا. `Subscription` تبقى على نسختها حتى renewal أو upgrade/downgrade صريح.

**الاستحقاقات** (`apps/subscriptions/entitlements.py`) — نقطة تحقّق واحدة: `require_feature(store, feature_key)` و`check_quota(store, quota_key, delta=1)`، بالضبط توقيع الوثيقة. تصنيف الحدود لفئتين حقيقيتين:
- **فئة A** (`products`) — `COUNT(*)` حي عبر registry (`register_live_counter`، تُسجِّله `apps.catalog.apps.CatalogConfig.ready()`) + `pg_advisory_xact_lock(hashtext(store_id), hashtext(quota_key))` (utility واحدة `apps/subscriptions/locks.py`، namespace موثَّق مركزيًا).
- **فئة B** (`orders_per_period`، أُعيدت تسميته من `orders_per_month` الحرفي في الوثيقة — الفترة الفعلية هي `Subscription.current_period_start/end`، ليست تقويمية) — عدّاد `UsageRecord` مقفَل بـ`select_for_update().get_or_create()`، نفس نمط `OrderNumberSequence` المُثبَت من Phase 8.

**نقاط الإنفاذ الفعلية** (تغطية DoD — القسم 6):
- `apps.catalog.services.create_product` → `check_quota("products")`.
- `apps.catalog.views.ProductDetailView.patch` → `check_quota_for_status_change` (يُنفَّذ **فقط** عند انتقال `archived → غير archived`؛ الأرشفة والانتقال الجانبي draft↔active غير محظورين أبدًا).
- `apps.orders.services._build_order` → `check_quota("orders_per_period")` + `require_active_store` (داخل نفس معاملة إنشاء Order — إعادة محاولة بنفس Idempotency-Key لا تستهلك الحدّ مرتين لأن `_build_order` لا يُعاد تنفيذها أصلًا).
- `apps.stores.mixins.StoreScopedAPIView` (كل كتابة dashboard عبر جميع التطبيقات) → `apps.stores.hooks.check_write_gates` → `require_active_store` (403→402 عند `Store.status == read_only`، القراءات تبقى مسموحة).

**دورة حياة الاشتراك** — 3 مفاهيم منفصلة كما اعتُمِد: `Subscription.status` (trialing/active/past_due/canceled)، `Store.status` (+`read_only` جديدة إضافية غير كاسرة، نفس نمط توسعة `Order.Status` في Phase 9)، ونتيجة فحص الاستحقاق (غير مخزَّنة، محسوبة حيًا). تجاوز حدّ لا يُغيِّر أي status أبدًا — يمنع الكتابة المحدَّدة فقط.

**المسح الزمني المُوصَّل بالكامل** (`apps/subscriptions/tasks.py`، نمط PlatformTask/TenantTask المُثبَت من Phase 9): انتهاء تجربة → `past_due`؛ `past_due` بعد `plan.grace_period_days` (حقل قابل للضبط، **لا** ثابت مُدمَج في FSM كما طلبتَ) → `Store.read_only`؛ اشتراك مُلغى بعد نهاية الفترة → `Store.read_only`؛ اشتراك نشط بعد نهاية الفترة → تدوير الفترة + تطبيق أي downgrade مجدوَل + إصدار Invoice إن كان السعر > 0.

**فجوة موثَّقة صراحة** (تعليمك بعدم الادّعاء بتغطية غير موجودة): `mark_past_due`/`mark_active` دوال حقيقية مُختبَرة مباشرة، لكن **لا مُطلِق فعلي** يستدعيها من حدث دفع حقيقي — لا يوجد تكامل مزوّد فوترة منصّة بعد (القسم 7). المسار الزمني (تجربة/نهاية فترة) هو الوحيد المُوصَّل بالكامل من طرف لطرف بلا اعتماد على مزوّد خارجي.

---

## 2. RLS — إثبات مباشر لكل ما طلبتَه (لا افتراض غياب سياسة الكتابة)

`apps/subscriptions/tests/test_plan_rls.py`، 8 اختبارات، تُثبِت **كلها** بالضبط ما طلبتَه:
1. `app_user` يقرأ Plans (SELECT مفتوحة).
2. INSERT على `app_user` **يرفع استثناء** (`new row violates row-level security policy`) — RLS ترفض الصف المُدرَج مباشرة لأنه لا يوجد ما يُقارَن به.
3. UPDATE/DELETE على `app_user` **لا يرفعان استثناء** بل يُصيبان **صفر صفوف** — سلوك RLS الحقيقي مختلف عن INSERT (موثَّق بالتفصيل في الاختبار): بلا سياسة مطابقة للأمر، الصف ببساطة غير مرئي لذلك الأمر. مُثبَت أن البيانات تبقى **بلا تغيير فعليًا** بعد المحاولة.
4. سياق tenant لا يُغيِّر شيئًا — لا في الرؤية ولا في الحظر.
5. **تحقّق صريح من GRANTs الفعلية** (طلبك المحدَّد): `has_table_privilege('app_user', 'subscriptions_plan', 'INSERT')` يُثبَت أنه **True** فعليًا (المنحة الجدولية العامة من `apps/tenancy/privileges.py` تشمل هذا الجدول)، ثم يُثبَت أن الكتابة **ترفض رغم ذلك** — RLS هو الحد الفعلي، وليس غياب GRANT.
6. `relrowsecurity` مفعَّلة فعليًا على الجداول الأربعة.

عزل tenant لـ`Subscription`/`UsageRecord`/`Invoice`: مُسجَّلة في `apps/subscriptions/tests/isolation_factories.py`، فرفعت مجموعة العزل العامة من **166 إلى 181** اختبارًا تلقائيًا (`test_every_tenant_owned_model_has_a_registered_isolation_factory` كان سيفشل لو نُسِيت). عزل entitlements عابر للمستأجرين مُثبَت إضافيًا مباشرة (`test_check_quota_never_reads_another_stores_subscription`).

---

## 3. Concurrency — الاختبارات الحقيقية المطلوبة (القسم 18، البندان 3 و4)

`apps/subscriptions/tests/test_concurrency.py` — نفس نمط Phase 5/8/9 المُثبَت (اتصالات `psycopg` مستقلة حقيقية، `app_migrator` للإعداد، `app_user` للتنافس، نفس تسلسل SQL الذي يُنفِّذه الكود الإنتاجي حرفيًا):

1. **`products` (فئة A)**: حد=1، فتحة واحدة متبقية، طلبا إنشاء متزامنان حقيقيان — واحد `created` والآخر `rejected` دائمًا، العدّ النهائي **لا يتجاوز الحد أبدًا** ولا يفقد الفائز.
2. **`orders_per_period` (فئة B)**: نفس السيناريو على `UsageRecord`. اختبار الإعداد الأول اكتشف أن `SELECT ... FOR UPDATE` **لا يقفل صفًا غير موجود بعد** — طلبا الإنشاء الأول لنفس الفترة يتسابقان على INSERT، فيُعاد إنتاج سلوك `get_or_create()` الداخلي في Django بدقة (SAVEPOINT، التقاط `UniqueViolation`، إعادة SELECT مع القفل) بدل افتراضه — وهذا بالضبط ما يفعله `_check_and_increment_usage_record` الإنتاجي فعليًا (يعتمد على `select_for_update().get_or_create()`، وليس تطبيقًا مبسَّطًا).

**3 تشغيلات متتالية** لملف التزامن — لا flakiness.

---

## 4. القرار التصميمي الذي صُحِّح أثناء البناء — اتجاه الاعتماد بين stores وsubscriptions

التصميم الأول: `apps.stores.services.create_store` يستورد `apps.subscriptions.services` مباشرة لتوفير الاشتراك التجريبي، **و** `apps.subscriptions.entitlements`/`tasks` تستورد `apps.stores.models.Store` (لأنها فعليًا تحتاج `Store.Status`/مسح `Store.objects`). هذا اعتماد **دائري** حقيقي بين الطبقتين — اكتُشِف فورًا عبر `import-linter` (`lint-imports`)، قبل أي commit، وليس عبر مراجعة يدوية.

**الحل**: عكس الاتجاه بالكامل — `apps.subscriptions` أصبح فوق `apps.stores` (نفس اتجاه كل تطبيق دومين آخر: catalog/orders/payments، لا استثناء خاص). التكامل العكسي (توفير الاشتراك عند إنشاء المتجر، ومنع الكتابة عند `read_only`) يمرّ عبر **سجلّين صريحين** يملكهما `apps.stores` نفسه (`apps/stores/hooks.py`: `register_post_creation_hook`/`run_post_creation_hooks` و`register_write_gate`/`check_write_gates`)، بنفس شكل `entitlements.register_live_counter` المُستخدَم أصلًا لـ`apps.catalog` — الطبقة الأدنى تُعرِّف نقطة التوسعة، الأعلى تُسجِّل فيها من `AppConfig.ready()` الخاصة بها. `apps.stores.services.create_store` و`apps.stores.mixins.StoreScopedAPIView` لا يستوردان `apps.subscriptions` إطلاقًا الآن. `import-linter` (10 عقود، صفر مخالفات) يفرض هذا بنيويًا، لا توثيقيًا فقط.

---

## 5. أخطاء أخرى وُجدت وأُصلحت أثناء البناء (كود اختبار، وتصحيح مبكر في الخدمة)

- **`services.publish_plan_version` كانت تكتب عبر `"default"` بدل `"migrator"`** — اكتُشِف عند كتابة `test_plan_version_isolation.py` (كان سيرفض أي استدعاء حقيقي، Plan/PlanVersion لا تقبل كتابة `app_user` إطلاقًا)، أُصلِح مؤقتًا بتحويلها لـ`"migrator"` صراحة. **مراجعتك اللاحقة (القسم 0.A.1) رفضت هذا الإصلاح المؤقَّت نفسه** كحدّ معماري — أُزيلت الدالة نهائيًا من `services.py`، واستُبدِلت بأمر إداري (`manage.py publish_plan_version`) لا علاقة له بطبقة الخدمة إطلاقًا.
- **`assert` في `entitlements.check_quota`** (bandit B101) — استُبدِل بـ`if/raise` صريح؛ `assert` يُحذَف كليًا تحت `python -O`، فكان سيتحوّل هذا الحارس إلى no-op صامت في وضع تشغيل معيّن.
- **دروس بنية اختبار** (لا تغيير إنتاجي): اتضح أن alias `"migrator"` و`"default"` في pytest-django كل منهما مُغلَّف بمعاملة **منفصلة غير مُلتزَمة** طوال الاختبار (حتى مع `TEST: {"MIRROR": "migrator"}`) — كتابة عبر أحدهما **غير مرئية** للآخر إطلاقًا داخل نفس الاختبار. الحل المُتَّبع في كل اختبارات Phase 10 التي تحتاج بيانات Plan مخصَّصة: اتصال `psycopg` خام بـ`autocommit=True` (نفس نمط `_insert_store` من Phase 8/9)، موثَّق بالتفصيل في `apps/subscriptions/tests/conftest.py`.

لا bugs إنتاجية بقيت غير مُصلَحة أو غير موثَّقة — القسمان أعلاه يغطيان كل ما وُجِد.

---

## 6. تغطية DoD — "فرض الحدود يعمل على كل المسارات المنطبقة فعليًا"

| الحدّ | مُنفَذ؟ | الدليل |
|---|---|---|
| `products` | ✅ كامل | إنشاء + أرشفة/إلغاء أرشفة عبر HTTP، تزامن حقيقي (§3) |
| `orders_per_period` | ✅ كامل | checkout/complete، idempotency، تزامن حقيقي (§3) |
| `staff` | ⚠️ نموذج فقط | **لا مسار كتابة حقيقي موجود** أصلًا في Phases 1-9 (لا staff-invite feature) — لا ادّعاء تغطية |
| `storage_mb` | ⚠️ نموذج فقط | **لا ميزة تخزين موجودة** لقياسها — غير قابل للتطبيق هذه المرحلة |
| `custom_domain`/`api_access` (features) | ⚠️ `require_feature` جاهزة ومُختبَرة | **لا مسار كتابة** (لا إضافة نطاق مخصَّص) يستدعيها بعد |
| `read_only` يمنع الكتابة/الشراء الجديد | ✅ كامل | dashboard (كل تطبيق عبر `StoreScopedAPIView`) + checkout + **`payments/initiate` (القسم 0.A.2، مُضاف في جولة المراجعة)**، القراءات + إكمال دفعات قائمة (webhook/reconciliation/COD capture) تبقى غير متأثرة عمدًا |

كل فجوة أعلاه **مذكورة صراحة في الكود نفسه** (docstrings) وليست صامتة.

---

## 7. Technical debt مؤجَّل عمدًا (موثَّق، لا افتراض تلقائي بالتوسّع)

| البند | لماذا |
|---|---|
| تحصيل فوترة فعلي (تكامل مزوّد دفع للمنصة) | DoD صريح "فرض الحدود"، ليس "الفوترة تعمل" — تفسير نطاق موثَّق هنا كما طلبتَ (القسم 15 من المراجعة) |
| واجهة platform-admin لإدارة Plans | لا `is_platform_staff`-based API موجودة أصلًا منذ Phase 2؛ Plans تُبذَر عبر migration، تُدار عبر **الأمر الإداري `manage.py publish_plan_version --database=migrator`** (القسم 0.A.1) — لا معماريّة كتابة platform-admin مُراجَعة بعد، ولن تُبنى بديلًا مؤقَّتًا هنا |
| `mark_past_due`/`mark_active` بلا مُطلِق فعلي من حدث دفع حقيقي | لا مزوّد فوترة منصّة بعد — المسار الزمني وحده مُوصَّل بالكامل |
| `staff`/`storage_mb`/`custom_domain`/`api_access` بلا مسار كتابة حقيقي | فجوات ميزات سابقة لـPhase 10، ليست إغفالًا فيه |
| `upgrade_subscription`/`schedule_downgrade` بلا endpoint تاجر ذاتي-خدمة | دوال حقيقية مُختبَرة، تكتبان فقط على `Subscription` (مسموح لـ`app_user`) — تُستدعيان اليوم فقط عبر شيفرة تشغيلية يدوية، بانتظار واجهة تاجر ذاتية-الخدمة مستقبلية |
| `SUSPENDED`/`CLOSED` على Store تبقيان بلا إنفاذ | فجوة موجودة مسبقًا قبل Phase 10 (موثَّقة أصلًا في docstring نموذج `Store`)، لم تُلمَس |

---

## 8. جميع الاختبارات ونتائجها

```
657 passed (3 تشغيلات متتالية مستقرة للمجموعة الكاملة، بعد جولة المراجعة)
```
- عزل tenant عام: **181** (بلا تغيير في جولة المراجعة)
- `test_plan_rls.py`: 8 — إثبات RLS المطلوب بدقة (القسم 2)، أُعيد تشغيله مباشرة بعد إزالة `publish_plan_version` من services.py — لا تأثر
- `test_entitlements.py`: 15 — check_quota/require_feature/require_active_store، عزل عابر للمستأجرين
- `test_concurrency.py`: 2 — الاثنان المطلوبان بدقة (القسم 3)
- `test_plan_version_isolation.py`: **8** (كانت 3؛ +5 في جولة المراجعة) — نسخة جديدة لا تُغيِّر اشتراكًا قائمًا، لا mutation في مكانها، نسخة `is_current` واحدة فقط، الأمر الإداري ينشر features أيضًا، يرفض JSON غير صالح، يرفض plan code غير موجود، يرفض العمل ضد alias غير migrator
- `test_tasks.py`: 8 — كل انتقالات المسح الزمني (تجربة/grace/إلغاء/تدوير فترة/فوترة/downgrade مجدوَل)
- `test_services.py`: 7 — دوال FSM/Invoice المتبقية + فرع `trial_days=0`
- `apps.catalog` — `test_product_quota.py`: 6 (إنشاء/أرشفة/إلغاء أرشفة/انتقال جانبي)
- `apps.orders` — `test_order_quota.py`: 3 (نجاح/حظر/idempotency بلا استهلاك مزدوج)
- `apps.stores` — `test_store_creation_atomicity.py`: 2، `test_store_read_only_gate.py`: 3
- **`apps.payments` — `test_read_only_gate.py`: 3، جديد (القسم 0.A.2)** — رفض بدء دفعة جديدة بلا أي أثر جانبي، متجر نشط غير متأثر، webhook على intent قائم يُكمِل بلا عائق

---

## 9. Coverage

```
98.26% إجمالاً (3383 عبارة، 59 غير مُغطاة — موروثة من مراحل سابقة)
apps/subscriptions/models.py                                   100%
apps/subscriptions/tasks.py                                    100%
apps/subscriptions/locks.py                                    100%
apps/subscriptions/apps.py                                     100% (كانت 88%)
apps/subscriptions/services.py                                 100% (كانت 94% -- الدالة المحذوفة كانت مصدر الفجوة)
apps/subscriptions/management/commands/publish_plan_version.py 100% (جديد)
apps/subscriptions/entitlements.py                              98%
```

---

## 10. Quality Gates

| البوّابة | النتيجة |
|---|---|
| ruff | ✅ نظيف |
| black | ✅ نظيف |
| mypy | ✅ نظيف (225 ملف مصدر، صفر أخطاء) |
| bandit | ✅ صفر مشاكل |
| import-linter | ✅ **10 عقود**، صفر مخالفات (بلا تغيير — `apps.payments` كان يستورد طبقات أدنى من `apps.subscriptions` أصلًا، لا عقد جديد لازم) |
| makemigrations --check | ✅ لا تغييرات مفقودة |
| pytest | ✅ 657/657، تغطية 98.26%، 3 تشغيلات متتالية للمجموعة الكاملة |
| ضمان عزل قاعدة اختبار PostgreSQL | ✅ نشط طوال المرحلة، لم يُلمَس |

---

## 11. القرارات المعمارية الجديدة

| القرار | السبب |
|---|---|
| `apps.subscriptions` فوق `apps.stores` في الطبقات (لا العكس) | تعارض اعتماد دائري حقيقي اكتُشِف عبر import-linter (القسم 4) — عُولِج ببنية، لا بتوثيق |
| `apps.stores.hooks` (سجلّان: post-creation + write-gate) | يُبقي `apps.stores` خاليًا من استيراد `apps.subscriptions` مع تمكين التكامل الحقيقي (توفير الاشتراك عند الإنشاء، حظر الكتابة عند read_only)، بنفس شكل `entitlements.register_live_counter` الأصلي |
| `check_quota_for_status_change` في `apps.catalog.services` بدل View | يُبقي الحكم التجاري (متى تُفحَص الحدود عند تغيير status) في طبقة الخدمة، لا الـView — نفس انضباط المشروع منذ Phase 4 |
| `orders_per_period` بدل `orders/month` الحرفي | الفترة الفعلية هي `current_period_start/end`، ليست تقويمية — الاسم لا يكذب على الدلالة |
| اتصال psycopg خام autocommit لبيانات اختبار Plan | `.using("migrator")` عبر ORM يبقى داخل معاملة pytest-django غير مُلتزَمة، غير مرئية لـ"default" — درس بنية اختبار حقيقي (القسم 5) |
| `publish_plan_version` كأمر إداري (`manage.py`)، لا دالة خدمة | جولة المراجعة (القسم 0.A.1): `app_migrator` لا يجوز أن يُفتَح من أي مسار خدمة تطبيق إنتاجي، مهما كانت الوجهة — فقط migrations/fixtures/إجراءات إدارية صريحة يُشغِّلها مشغِّل بشري |
| `require_active_store` داخل `apps.payments.services.initiate_payment` (سطر أول، قبل أي أثر جانبي) | جولة المراجعة (القسم 0.A.2): بدء دفعة جديدة هو "شراء جديد"، يجب أن يُمنَع على متجر read_only مثل checkout تمامًا — لا يُطبَّق على process_webhook/reconciliation/COD capture لأنها تُكمِل عمليات قائمة، لا تبدأ عملية جديدة |

---

## المرحلة التالية

بانتظار موافقتك الصريحة قبل تحديد المرحلة التالية حسب خارطة الطريق.
