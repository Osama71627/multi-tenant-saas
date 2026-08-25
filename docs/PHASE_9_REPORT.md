# Phase 9 Report — Payments

**التاريخ:** 2026-08-22
**الحالة:** ✅ مكتملة بعد جولة مراجعة (REQUEST CHANGES) طبَّقت تصحيحًا معماريًا إلزاميًا لدورة حياة COD + اختبار أمان HTTP عابر للمستأجرين إلزاميًا للـwebhook — **582/582** اختبار ناجح فعليًا ضد PostgreSQL حقيقي (كانت 458 في نهاية Phase 8؛ +116 في التنفيذ الأول؛ +8 في جولة المراجعة = 582)، 3 تشغيلات متتالية مستقرة، تغطية 98% إجمالاً و**100%** لكل ملفات `apps.orders` و`apps.payments`، كل بوّابات الجودة خضراء. **3 bugs إنتاجية حقيقية** وُجدت وأُصلحت أثناء البناء الأول (القسم 5) + **قرار معماري حقيقي صُحِّح** في جولة المراجعة (القسم 0.A) — أهمها فجوة RLS كانت ستُصمِت مهمة المصالحة بالكامل في الإنتاج.

---

## 0.A جولة المراجعة (REQUEST CHANGES) — النقطتان، مُغلَقتان

### 0.A.1 تصحيح دورة حياة COD — قرار معماري حقيقي، ليس bug

التصميم الأول كان: `COD مُختارة → PaymentIntent.processing → تحصيل النقد بعد التسليم → capture → تأكيد الطلب + تفعيل المخزون`. رُفِض هذا صراحة لأنه يُؤخِّر تأكيد الطلب والتزام المخزون حتى **بعد** التسليم الفعلي — بينما "قبول COD كوسيلة دفع" و"تحصيل النقد فعليًا" حدثان تجاريان منفصلان.

**الدلالات المعتمَدة الآن**:
- **قبول COD** (لحظة `create_payment`، `PaymentIntent` تبقى `processing`): الطلب يصبح `confirmed` **فورًا**، وحجوزات المخزون تُفعَّل (`fulfilled`) **مرة واحدة فقط**، بلا أي ادّعاء بأن النقد قد تحرَّك.
- **تحصيل COD** (فعل تاجري لاحق صريح عبر `capture-cod`): `PaymentIntent` فقط تنتقل إلى `succeeded` — **لا** استدعاء ثانٍ لـ`confirm_order`، **لا** تفعيل ثانٍ للمخزون.

**التنفيذ**: أُضيفت خاصية جديدة لواجهة المزوّد `ProviderCapabilities.confirms_order_on_acceptance` (`True` لـ`ManualCodProvider` فقط؛ `False` للجميع). `initiate_payment` تستدعي `confirm_order` أيضًا عندما `state == processing` **و** هذه الخاصية صحيحة، وليس فقط عند `succeeded`. **لم يُضَف أي state جديد** (لا `confirmed_unpaid` ولا غيرها) — `PaymentIntent.state == processing` على طلب **بالفعل** `confirmed` يُمثِّل "غير مدفوع، بانتظار التحصيل" بالكامل، تمامًا كما طلبتَ. الحماية من تكرار الأثر عند التحصيل اللاحق **موجودة أصلًا** بلا أي كود إضافي: حارس `apply_payment_transition` الحالي ("لا تُفعِّل إلا إذا كان الطلب لا يزال `pending_payment`") يمنع إعادة التأكيد تلقائيًا لأن الطلب غادر تلك الحالة عند القبول.

**لا FSM جديد انفتح**: لم يظهر أي قرار حالة إضافي صعب التراجع أثناء هذا التصحيح — تعديل واحد محدود (خاصية provider + شرط واحد إضافي في `initiate_payment`) كافٍ تمامًا.

**5 اختبارات regression جديدة** (`test_manual_cod_capture.py`، مُعاد كتابته بالكامل) تُثبِت الخمسة المطلوبة حرفيًا: (1) القبول يُؤكِّد الطلب فورًا، (2) المخزون يُفعَّل مرة واحدة عند القبول، (3) `PaymentIntent` تبقى `processing` بعد القبول وحده، (4) التحصيل اللاحق يُغيِّر حالة الدفع فقط، (5) تحصيل مكرَّر لا يُكرِّر تأكيد الطلب أو تفعيل المخزون (مُثبَت بطلبي `capture` متتاليين حقيقيين عبر HTTP).

### 0.A.2 اختبار عزل HTTP عابر للمستأجرين لمسار webhook — أُضيف

ملف جديد `apps/payments/tests/test_webhook_cross_tenant.py` — متجران كاملان حقيقيان (كل منهما بحساب تاجر، منتج، شحن، Order، PaymentIntent، ومفتاح webhook سرّي **مستقل**)، 3 اختبارات:
1. حمولة موقَّعة بمفتاح متجر A **الحقيقي الصالح لمسار A نفسه**، لكن تشير إلى `provider_ref` الحقيقي لمتجر B + بيانات وصفية مزوَّرة تدّعي `store_id=B` — تُرسَل عبر مسار A. النتيجة: **صفر أثر** على PaymentIntent متجر B (وB لا يوجد أي مسار للوصول إليه أصلًا بمعزل الـtenant).
2. نفس الهجوم بالاتجاه المعاكس (سر متجر B الحقيقي، `provider_ref` متجر A، عبر مسار B).
3. تأكيد أن سر متجر B **لا يُتحقَّق أبدًا** أمام مسار متجر A (400 توقيع خاطئ) — يُثبت أن السرّين مستقلان فعليًا، وليس فقط طبقة الربط.

التوقيع في كل الحالات صالح **تشفيريًا** أمام المتجر الذي يُهاجَم مساره — بالضبط كما طلبتَ، حتى يصل الاختبار فعليًا إلى منطق الربط/tenant بدل التوقف عند فشل التوقيع فقط. اختبارات RLS العامة (§2) أُبقيت كما هي كدفاع إضافي في العمق.

---

## 0. مسار الاعتماد

عُرض مقترح معماري كامل (17 نقطة) بناءً على قراءة فعلية لـ§8 (Payment Architecture)، §5.2/5.3 (API)، §12 (نموذج التهديد)، §14 (استراتيجية الاختبار)، §16 (المخاطر)، وسطر Phase 9 في خارطة الطريق، بالإضافة لفحص الكود الفعلي (لا Celery queues مخصَّصة، لا مكتبة تشفير، لا حزمة `stripe`، `Order.status` يحمل قيمة واحدة فقط). اعتُمد المقترح مع تعديلات إلزامية مفصَّلة لكل بند (حدود `apps.payments`، FSM صريح غير رقمي، فصل Order FSM عن Payment FSM، COD منفصل عن apps.orders، idempotency بمعزل عن `apps.orders.IdempotencyKey`، ترتيب تحقق webhook محدَّد، namespace صحيح لتفرّد الحدث، سياسة مخزون واضحة، معالجة dual-write صريحة، reconciliation إلزامية بالحد الأدنى، تشفير AES-GCM، اختبار Stripe بلا شبكة حقيقية، لا refund endpoint، و3 اختبارات تزامن محدَّدة بدقة). كل تعديل مُطبَّق حرفيًا أدناه.

---

## 1. ما تم تنفيذه فعليًا

### apps.payments (تطبيق جديد، يعتمد على apps.orders فقط)

**النماذج**: `StoreProviderConfig`, `PaymentIntent`, `PaymentTransaction`, `WebhookEvent`, `PaymentIdempotencyKey` — كلها `TenantOwnedModel`، RLS كاملة. `PaymentIntent.amount/currency` لقطة من `Order` عند الإنشاء. قيد DB جزئي: `PaymentIntent` واحدة فقط بحالة `processing` لكل Order (يمنع تكرار محاولات دفع نشطة من إعادة محاولة). `WebhookEvent` تفرّده `(provider_config, external_id)` — namespace المزوّد الصحيح، وليس تفرّدًا عامًا.

**Provider abstraction** (`apps/payments/providers/`): ABC موحَّد (`create_payment`, `capture`, `refund`, `check_status`, `verify_webhook`, `map_event`, `capabilities`) + `MockProvider` (HMAC حقيقي، سلوك غير متزامن يحاكي مزوّدًا حقيقيًا) + `ManualCodProvider` (COD) + `StripeProvider` (SDK رسمي حقيقي، لا حساب global `stripe.api_key` أبدًا — كل استدعاء يمرّر `api_key` صريحًا لأن كل متجر له مفتاحه الخاص).

**Payment FSM صريح، غير رقمي** (`_ALLOWED_TRANSITIONS` — خريطة انتقالات حرفية): `processing → {succeeded, failed, cancelled}` فقط، وكل الحالات الثلاث الأخيرة نهائية. `apply_payment_transition` هي **المكان الوحيد** الذي يُغيّر `PaymentIntent.state` أو يُصعِّد إلى Order/المخزون — يُقفَل صفّها أولًا، ويُتحقَّق من حالتها **الحالية** قبل أي تغيير، فيكون آمنًا تحت تزامن حقيقي **بمعزل** عن تفرّد `WebhookEvent` (بالضبط ما طلبتَه).

**Order FSM منفصل تمامًا**: أُضيفت دالتان جديدتان فقط إلى `apps.orders.services` (وليس إلى apps.payments): `confirm_order`/`cancel_order` — تقفلان Order، تتحققان أنها `pending_payment`، ثم تُطبّقان النتيجة **وتُفعِّلان/تُحرِّران حجوزات المخزون** (نفس آلية Phase 8 دون تكرار). `apps.payments` يستدعيهما فقط، لا يُعدِّل `Order.status` مباشرة أبدًا.

**COD منفصل عن apps.orders**: `checkout/complete` (Phase 8) يبقى كما هو تمامًا — لا يعرف شيئًا عن الدفع. `POST storefront/payments/initiate` (بعد إنشاء Order) هو ما يختار Stripe أو COD وينشئ `PaymentIntent`. **دورة حياة COD المُصحَّحة في جولة المراجعة (القسم 0.A.1)**: قبول COD (`create_payment` → `processing`) يُؤكِّد الطلب ويُفعِّل المخزون **فورًا**، لا بعد التسليم؛ تحصيل النقد فعليًا (`capture` عبر endpoint دفة منفصل `POST .../payment-intents/{id}/capture-cod`، فعل تاجر صريح فقط) يُغيِّر حالة الدفع فقط، بلا تكرار أي أثر.

**Idempotency بمعزل عن Phase 8**: `PaymentIdempotencyKey` نموذج مستقل خاص بـ`apps.payments` (نفس شكل/خوارزمية Phase 8 المثبَتة، بصمة مختلفة: `order_id + provider_key`) — **لا** استيراد لـ`apps.orders.IdempotencyKey`. `initiate_payment` ينقسم إلى **3 معاملات قصيرة** حول استدعاء شبكي واحد بلا معاملة مفتوحة (القسم 6).

**معالجة Dual-write**: `provider_idempotency_key` يُشتَق من Idempotency-Key الخاص بالعميل نفسه (`f"{store.id}:{idempotency_key}"`) — إعادة محاولة (من العميل أو من استرداد بعد عطل) تصل للمزوّد بنفس المفتاح دائمًا، فيتولى المزوّد نفسه منع دفعة مزدوجة، بغض النظر عن ارتباك حالتنا المحلية.

**Webhooks** (`POST webhooks/payments/{provider}/{store_id}`): مسار تحليل tenant ثالث جديد أُضيف إلى `TenantMiddleware` (بجانب dashboard/storefront) — `store_id` في المسار **لا يُستخدَم كحد أمني إطلاقًا**، فقط لتحديد `StoreProviderConfig` الصحيح الذي يُتحقَّق التوقيع أمامه. الترتيب حرفيًا كما طلبتَ: تحليل provider_config من المسار ← تحقّق التوقيع على raw body ← ربط `provider_ref` (محلي، وليس من الحمولة) ← تحقّق tenant صريح ← تحقّق مبلغ/عملة حرفي ← تحقّق انتقال FSM مسموح.

**Reconciliation (إلزامي، الحد الأدنى)**: `apps.payments.tasks.reconcile_stuck_payment_intents` (كل 30 دقيقة عتبة) يستخدم **نفس** `apply_payment_transition` التي يستخدمها webhook — لا منطق انتقال ثانٍ. `manual_cod` مُستبعَدة (`capabilities.requires_webhook`) لأنه لا شيء خارجي لاستطلاعه.

**التشفير** (`apps/payments/encryption.py`): AES-256-GCM، nonce عشوائي لكل استدعاء، مصادَق (GCM tag)، مغلَّف بإصدار (`v1:nonce:ciphertext`)، مفتاح من env وليس DB، رسائل الخطأ لا تحوي نصًا صريحًا أو مفتاحًا أبدًا. `credentials`/`webhook_secret` write-only بالكامل في الـAPI — `credentials_hint` فقط (مُحسَبة مرة واحدة عند الكتابة) يُعاد عرضها.

---

## 2. RLS والعزل — مُختبَر فعليًا لكل الجداول الخمسة الجديدة

سُجِّلت في `apps/payments/tests/isolation_factories.py`، مجموعة العزل العامة صارت **166 اختبارًا** (كانت 141). لا اختبارات HTTP عابرة إضافية خاصة بـpayments كانت ضرورية إذ أن كل الأسطح (storefront/dashboard/webhook) تُعيد استخدام آليات تحليل tenant المُثبَتة مسبقًا (Phase 6/8) بلا تعديل جوهري، عدا مسار webhook الجديد الموثَّق أدناه.

---

## 3. مسار Tenant الثالث: Webhooks — تعديل على `TenantMiddleware`

لم يكن هناك مسار تحليل tenant لهذا السطح أصلًا قبل الآن (فقط dashboard/storefront). أُضيف نمط regex ثالث صريح (`/api/v1/webhooks/payments/<provider>/<uuid>`) بنفس آلية `_resolve_by_id` الحالية — **سبب تقني حقيقي**، وليس إعادة فتح غير مبرَّرة: endpoint جديد بالكامل يحتاج تحليل tenant، ولا Host ولا مستخدم مُصادَق متاحَين لهذا السطح. `WebhookAPIView` جديدة في `apps/stores/mixins.py` (نفس نمط `StorefrontAPIView`، `AllowAny`، توضيح صريح أن `store_id` ليس حدًا أمنيًا).

---

## 4. Concurrency — الثلاثة invariants الحقيقية المطلوبة بدقة

`apps/payments/tests/test_concurrency.py` — نفس نمط Phase 5/8 المُثبَت (اتصالات مستقلة حقيقية، `app_migrator` للإعداد، `app_user` للتنافس):

1. **Webhook مكرَّر بنفس هوية الحدث**: طلبان متزامنان حقيقيان بنفس `external_id` — واحد `processed`، الآخر `duplicate` (attempts++)، صف `WebhookEvent` واحد، `PaymentTransaction` واحدة فقط، لا ازدواج.
2. **نجاح webhook يتسابق مع فشل reconciliation لنفس PaymentIntent**: أُثبِت أن الحالة النهائية **متسقة داخليًا دائمًا** — إما (`succeeded` + حجز `fulfilled` + `on_hand`/`reserved` منخفضان معًا) أو (`failed` + حجز `released` + `reserved` فقط منخفض) — لا مزيج أبدًا. هذا الاختبار يُثبت حرفيًا الشرط الذي طلبتَه: "لا يمكن أن يصبح الدفع ناجحًا بينما reservation تم release لها".
3. **حدثان مختلفان (external_id مختلف) لنفس النجاح**: يُثبَت أن `on_hand` ينخفض **مرة واحدة فقط** رغم وصول حدثين ناجحين متزامنين — الحماية من `apply_payment_transition`'s القفل على `PaymentIntent` نفسه، **وليس** من تفرّد `WebhookEvent` (الذي لا ينطبق أصلًا هنا لاختلاف الـid). بالضبط الشرط الثالث الذي طلبتَه.

**6 تشغيلات متتالية** لهذا الملف — لا flakiness.

---

## 5. Bugs — 3 bugs إنتاجية حقيقية وُجدت وأُصلحت أثناء البناء

### 5.1 فجوة RLS في مهمة المصالحة (الأخطر) — كانت ستُصمِت الميزة بالكامل في الإنتاج

التصميم الأول استخدم `PaymentIntent.unscoped.filter(...)` داخل `PlatformTask` (بلا سياق tenant) لمسح كل المتاجر دفعة واحدة. عند التشغيل الفعلي، أعاد **صفر** صفوف رغم وجود PaymentIntents عالقة حقيقية. السبب: `.unscoped` **لا يتجاوز RLS** (موثَّق صراحة في `apps/tenancy/models.py`) — فقط الفلترة على مستوى Python. بلا GUC مضبوط، سياسة RLS ترفض كل الصفوف. **الإصلاح**: `reconcile_stuck_payment_intents` يُكرِّر على `Store.objects.filter(status=active)` (الجدول الوحيد المفتوح RLS-يًا)، ويضبط سياق tenant حقيقيًا لكل متجر على حدة قبل الاستعلام — بنفس الأداة التي يستخدمها `TenantTask.__call__` داخليًا، **وليس** عبر اتصال `app_migrator` (كان سيخلط حد "migrator لِلمخطَّط فقط" الذي حافظ عليه المشروع منذ Phase 1). اختبار regression مباشر يثبت أن المسح يعمل الآن فعليًا.

### 5.2 خطأ 500 بدل 400 عند تكرار provider_key

`StoreProviderConfigListCreateView.post` لم يكن يلتقط `IntegrityError` من قيد `uniq_provider_config_per_store`، فيُرجِع 500 خامًا بدل 400 واضح. أُصلِح بنفس نمط `ShippingRateListCreateView` (Phase 7) — التقاط `IntegrityError` صريح، رسالة واضحة.

### 5.3 حدث webhook غير معروف كان سيُعامَل خطأً كفشل دفع

`_apply_domain_event` الأصلية كانت: `target_state = succeeded إن كان kind == "payment_succeeded" وإلا failed` — أي أن أي نوع حدث **آخر** غير معروف (مثل `payment_intent.created` الحقيقي في Stripe، إن أرسل التاجر كل الأحداث لنفس الـendpoint) كان سيُعامَل كفشل دفع **ويُلغي الطلب فعليًا**. اكتُشِف أثناء كتابة اختبار تغطية لفرع "unhandled" في `StripeProvider.map_event`. **الإصلاح**: حارس صريح يتجاهل أي `kind` ليس `payment_succeeded`/`payment_failed` — يُسجَّل `WebhookEvent` للتدقيق، بلا أي أثر على `PaymentIntent`/`Order`. اختبار regression مباشر يثبت عدم التراجع.

### أخطاء إضافية في كود الاختبار نفسه (وليس الإنتاجي)

نفس نمط كل مرحلة سابقة: استدعاء `create_order`/`add_stock`/`setup_flat_shipping` أكثر من مرة لنفس المتجر كشف قيود تفرّد لم تكن الاختبارات تتوقعها (اسم موقع مخزون مكرَّر، منطقة شحن مكرَّرة تكسر tie-break الأولوية). صُحِّحت الدوال المساعدة في `conftest.py` لتكون idempotent (إعادة استخدام الموجود بدل إعادة الإنشاء) — لا تغيير على الكود الإنتاجي.

---

## 6. معاملات قصيرة حول استدعاء الشبكة — لا قفل DB أثناء انتظار المزوّد

`initiate_payment` مُصمَّمة صراحة بثلاث معاملات منفصلة: (1) مطالبة idempotency (DB فقط) ← (2) استدعاء `provider.create_payment` **بلا** أي `transaction.atomic()` مفتوحة ← (3) حفظ النتيجة (DB فقط). هذا يعني أن حالة "لا يزال قيد المعالجة" (`still being processed`) هنا **حقيقية وقابلة للوصول فعليًا** (بخلاف Phase 8 حيث كانت دفاعية فقط) — لأن نافذة الشبكة الحقيقية بين الخطوتين 1 و3 تعني أن مطالبة idempotency-key متزامنة أخرى تراها فعلاً `pending`. مُختبَر صراحةً.

---

## 7. جميع الاختبارات ونتائجها

```
582 passed (3 تشغيلات متتالية مستقرة للمجموعة الكاملة)
```
- عزل tenant عام: 166 (كانت 141 + 25 جديدة لـ5 جداول payments)
- `test_encryption.py`: 11 — تشفير/فك، nonce عشوائي، عبث بالبيانات، مفتاح خاطئ الطول/الترميز، لا تسريب في رسائل الخطأ، إخفاء جزئي
- `test_providers.py`: 32 — Mock/ManualCod/Stripe (SDK حقيقي مع mock على حدود الشبكة فقط)، توقيع Stripe حقيقي مبني يدويًا بخوارزمية Stripe الرسمية، `stripe.api_key` العام لا يُمَس أبدًا، سجل provider، `confirms_order_on_acceptance` (جديد، القسم 0.A.1)
- `test_transition_fsm.py`: 8 — نجاح يُفعِّل الحجز، فشل قابل لإعادة المحاولة يُبقي الطلب معلَّقًا، فشل غير قابل يُلغي، إعادة تطبيق حالة نهائية no-op، حدث خارج الترتيب لا يتراجع، `cancelled`، حدث غير معروف لا يُعامَل كفشل (5.3)
- `test_initiate_payment.py`: 14 — mock/COD، idempotency (تكرار، تعارض جلسة مختلفة، لا يزال قيد المعالجة)، منع محاولة دفع نشطة مكرَّرة، Order غير قابل للدفع، مزوّد غير مُهيَّأ، فك تشفير Stripe الفعلي، نجاح متزامن افتراضي
- `test_webhook.py`: 9 — نجاح حقيقي، توقيع خاطئ، تسليم مكرَّر، عدم تطابق مبلغ، provider_ref غير معروف، متجر/مزوّد غير موجودين
- `test_manual_cod_capture.py`: 8 (أُعيد كتابته بالكامل في جولة المراجعة) — الخمسة regression المطلوبة صراحة (القسم 0.A.1) + رفض intent غير-COD + 404 + 403
- `test_webhook_cross_tenant.py`: **3، جديد** (القسم 0.A.2) — عزل HTTP حقيقي بمتجرين كاملين
- `test_provider_config.py`: 5 — لا سرّ في الاستجابة أبدًا، تشفير حقيقي في DB، تكرار مرفوض، 403
- `test_reconciliation.py`: 7 — مسح صحيح، تجاهل حديث، تجاهل مزوّد معطَّل، تجاهل COD، حل فعلي، عدم إعادة معالجة محلولة
- `test_concurrency.py`: 3 — الثلاثة invariants (القسم 4)
- `apps.orders` إضافات: `confirm_order`/`cancel_order` على طلب غير `pending_payment` يرفعان الخطأ الصحيح

---

## 8. Coverage

```
98% إجمالاً (2995 عبارة، 58 غير مُغطاة -- موروثة من مراحل سابقة، غير متعلقة بـPhase 9)
apps/orders/*    100% (شامل confirm_order/cancel_order الجديدتين)
apps/payments/*  100% في كل ملف (شامل confirms_order_on_acceptance الجديدة)
```

---

## 9. Quality Gates

| البوّابة | النتيجة |
|---|---|
| ruff | ✅ نظيف |
| black | ✅ نظيف |
| mypy | ✅ نظيف (63 ملفًا في payments/orders/stores، صفر أخطاء) |
| bandit | ✅ صفر مشاكل (استثناء واحد موثَّق: `secret_key=""` افتراضي غير حسّاس) |
| import-linter | ✅ 9 عقود، صفر مخالفات |
| makemigrations --check | ✅ لا تغييرات مفقودة (تعديلات جولة المراجعة كود Python بحت، بلا تغيير نماذج) |
| pytest | ✅ 582/582، تغطية 98%، 3 تشغيلات متتالية للمجموعة الكاملة + إعادة تشغيل مباشرة لكل ملفات التزامن/الأمان الحرجة |
| ضمان عزل قاعدة اختبار PostgreSQL | ✅ نشط طوال المرحلة، لم يُلمَس |

---

## 10. القرارات المعمارية الجديدة

| القرار | السبب |
|---|---|
| مسار tenant ثالث (`webhooks/payments/...`) في `TenantMiddleware` | سبب تقني حقيقي: سطح جديد بالكامل بلا Host/مستخدم مُصادَق |
| `PaymentIdempotencyKey` مستقل عن `apps.orders.IdempotencyKey` | تعليمك الصريح — semantics مختلفة (order+provider، لا session)، لا اعتماد طويل الأمد على تفصيل تنفيذ في تطبيق آخر |
| `confirm_order`/`cancel_order` في `apps.orders`، لا في `apps.payments` | يبقي قواعد صحة Order FSM في مكان واحد؛ apps.payments يستدعيها، لا يُعيد تنفيذها |
| `check_status` أُضيفت لـABC (لم تكن في المقترح الأصلي) | مطلوبة فعليًا لمهمة المصالحة الإلزامية؛ استُنتِجَت من DoD لا افتُرِضَت |
| ترتيب قفل ثابت: PaymentIntent قبل Order دائمًا | يمنع deadlock؛ نفس مبدأ Phase 8's CartItem-قبل-CheckoutSession |
| `ProviderCapabilities.confirms_order_on_acceptance` (جولة المراجعة) | يفصل "قبول COD" عن "تحصيل COD" دون إضافة state جديد؛ عام بما يكفي لأي مزوّد مستقبلي بنفس الشكل (COD-like)، لا خاص بـ`manual_cod` حصرًا |

---

## 11. ما تم اختباره فعليًا / ما لم يتم

**تم اختباره فعليًا**: كل تدفّق دفع عبر HTTP حقيقي (mock وCOD بدلالاته المُصحَّحة — القسم 0.A.1)، Stripe الحقيقي بحدود SDK مُحاكاة فقط (لا شبكة)، الثلاثة invariants الحقيقية للتزامن، RLS (عام + HTTP عابر للمستأجرين حقيقي لمسار webhook تحديدًا — القسم 0.A.2)، تشفير حقيقي في DB، مصالحة حقيقية (Celery eager)، dual-write عبر مفتاح idempotency مُشتَق.

**لم يتم اختباره / خارج النطاق عمدًا**:
- لا اتصال شبكة حقيقي بـStripe (قرار معتمَد صراحة).
- لا refund endpoint فعلي (البنية موجودة، غير مُفعَّلة).
- لا partial capture/refund.
- لا Shipment/Fulfillment.
- Docker غير مُختبَر فعليًا (مستمر منذ Phase 1).

---

## 12. Technical debt مؤجَّل عمدًا

| البند | لماذا |
|---|---|
| Refund endpoint فعلي | لم يُطلَب صراحة في DoD Phase 9 |
| Reconciliation متقدمة (تسوية دورية شاملة، لا فقط `processing` عالقة) | "الحد الأدنى" فقط مطلوب لهذه المرحلة |
| KMS لتشفير بيانات الاعتماد | env var كافٍ لـv1، معتمَد صراحة |
| Partial capture/refund architecture | لا متطلَّب فعلي بعد |

---

## المرحلة التالية

بانتظار موافقتك الصريحة قبل تحديد المرحلة التالية حسب خارطة الطريق.
