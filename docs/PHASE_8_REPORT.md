# Phase 8 Report — Checkout & Orders

**التاريخ:** 2026-08-22
**الحالة:** ✅ مكتملة بعد جولة مراجعة (REQUEST CHANGES) طبَّقت 3 تصحيحات إلزامية — 458/458 اختبار ناجح فعليًا ضد PostgreSQL حقيقي، 3 تشغيلات متتالية مستقرة، تغطية 98% إجمالاً و**100%** لكل ملفات `apps.orders`، كل بوّابات الجودة خضراء. **تصحيح جوهري من جولة المراجعة**: تحليل النقطة 2 (أدناه، القسم 0.A.1) كشف race condition حقيقيًا في `checkout_complete` — تم إصلاح جذره وإثباته باختبار تزامن حقيقي، وليس مجرد "تحقّق" من سلوك كان آمنًا أصلًا.

---

## 0.A جولة المراجعة (REQUEST CHANGES) — الثلاث نقاط، مُغلَقة

### 0.1 CheckoutSession single-order invariant — **bug حقيقي وُجِد وأُصلِح، ليس مجرد توثيق**

طلبتَ التحقّق الدقيق بدل الوثوق بالتقرير الأول. التحليل الدقيق كشف ما يلي:

**الاختبار الأصلي `test_completing_twice_with_different_keys_after_success_is_404` كان *تسلسليًا*** (الطلب الأول يكتمل ويُثبَّت commit بالكامل، **ثم** يبدأ الثاني) — وهذا يثبت فقط أن إعادة المحاولة التسلسلية آمنة، **وليس** أن تزامنًا حقيقيًا آمن.

**التحليل الدقيق لكود `checkout_complete` الأصلي كشف ثغرة تزامن حقيقية:** الحارس `if session.status != ACTIVE` كان يفحص كائن `session` الذي جُلِب **بلا قفل** في بداية الدالة — أي قبل قفل `IdempotencyKey` وقبل قفل `CartItem` داخل `_build_order`. مفتاحا Idempotency-Key **مختلفان** لا يتصادمان على قيد `(store, key)`، فكلا الطلبين يمرّان من فحص Idempotency بلا تعارض، ثم كلاهما يقرأ نفس القيمة القديمة `active` من نفس كائن `session` غير المُقفَل. النتيجة: طلبا `complete` متزامنان حقيقيان (وليس متتاليان) على **نفس** CheckoutSession، بمفتاحين مختلفين، كانا قادرين نظريًا على إنتاج **طلبين ناجحين** من جلسة checkout واحدة — مخالفة صريحة للـinvariant المطلوب.

**الإصلاح الجذري**: أُضيف `CheckoutSession.objects.select_for_update()` — إعادة جلب وقفل الجلسة **داخل نفس معاملة** `checkout_complete`، بعد نجاح مطالبة Idempotency-Key وقبل استدعاء `_build_order`. الآن: طلب متزامن ثانٍ يُحجَب على قفل صف CheckoutSession نفسه حتى تُغلَق معاملة الأول، فيرى الحالة الحقيقية بعد الالتزام (`completed`) ويُرفَض بشكل صحيح. **هذا الآن invariant مدعوم بقفل DB حقيقي، وليس اعتمادًا على تطابق Idempotency-Key** — بالضبط ما طلبتَه.

**اختبار تزامن حقيقي جديد** (`test_two_concurrent_completes_on_the_same_session_only_one_ever_builds_an_order`, القسم 4 أدناه) يثبت الإصلاح باتصالات PostgreSQL مستقلة حقيقية: طلبان متزامنان فعليًا على نفس CheckoutSession — واحد فقط `completed`، الآخر `rejected`، الحالة النهائية `completed` بلا ازدواج.

**لم يُمَس** الاختبار التسلسلي الأصلي (لا يزال صحيحًا كخاصية أضعف)، ولم تُعَد فتح أي قرار معماري آخر من Phase 8.

### 0.2 OrderNumberSequence concurrency — اختبار جديد مُضاف

`test_order_number_sequence_under_two_concurrent_checkouts_never_collides` (القسم 4 أدناه) — نفس Store، اتصالان مستقلان حقيقيان يتنافسان على نفس صف `OrderNumberSequence` بنفس تسلسل القفل الذي تنفّذه `_next_order_number` فعليًا (`SELECT ... FOR UPDATE`، زيادة، حفظ). أُثبِت: كلا المحاولتين تنجحان، رقمان مختلفان (`[1, 2]`)، لا زيادة مفقودة، لا تكرار، **لا `IntegrityError` يتسرّب** (مصفوفة `errors` فارغة صراحة)، والتسلسل ينتهي بالقيمة الصحيحة (`2`). قيد `UniqueConstraint(store, number)` على `Order` بقي كما هو كدفاع إضافي (دفاع في العمق)، لكنه لم يكن بديلاً عن اختبار الـallocator نفسه.

### 0.3 Test-count provenance — تصحيح

الرقم المعتمَد رسميًا في اعتمادك لـPhase 7 كان **392/392**. بعد ذلك الاعتماد مباشرة، وبناءً على طلبك الصريح ("يمكن إصلاحه كـcleanup صغير قبل/مع بداية Phase 8")، أُضيف اختبار واحد (`test_find_matching_zone_tie_break_on_equal_priority_is_deterministic`) لإثبات deterministic tie-break — موثَّق في `docs/PHASE_7_REPORT.md` القسم 10 (Addendum) بنتيجة **393/393**. هذا هو المصدر الوحيد للفارق بين 392 و393: اختبار واحد إضافي طلبتَه أنت بنفسك بعد الاعتماد مباشرة، وليس خطأ عدّ أو تعديلًا غير موثَّق. Phase 8 بدأت من هذا الأساس المُوثَّق (393)، وأضافت 63 اختبارًا جديدًا (456)، ثم جولة المراجعة الحالية أضافت اختبارين آخرين (458): `393 + 63 + 2 = 458`.

---

## 0.B مسار الاعتماد الأصلي: Architecture Proposal ثم موافقة بتعديلات إلزامية

قبل أي كتابة كود، عُرض عليك مقترح معماري كامل (16 نقطة: Order/OrderItem aggregate، snapshots مالية، عناوين، شحن، CheckoutSession، تزامن، إلخ) بناءً على قراءة فعلية لـ`docs/ARCHITECTURE.md` (القسم 4 "Database Architecture"، القسم 5.2/5.3 "API"، القسم 8 "Payment"، القسم 12 "Security"، القسم 16 "Risks"، وصف Phase 7، وسطر Phase 8 في خارطة الطريق). اعتمدتَ المقترح مع **16 تعديلًا إلزاميًا** (Guest checkout فقط، JSONB snapshots بلا `CustomerAddress`، عدم الثقة بـ`/cart/shipping-quotes`، `CheckoutSession` بـRLS و`expires_at` على مستوى DB، **رفض `first active StockLocation`** لصالح "أول موقع يكفي الكمية كاملة بترتيب حتمي"، فحص semantics حقيقي لـ`StockReservation.reference` قبل استخدامه، DB-backed idempotency وليس Redis فقط، عدم استخدام `reprice_cart` لتجنّب mutation غير ضرورية على Cart، `Coupon.times_used` ضمن نفس معاملة إنشاء الطلب، سياسة ضريبة v1 صريحة (`tax base = بعد الخصم، الشحن مستبعد`)، لا COD/لا `confirmed` في Phase 8، لا `Shipment`/`Fulfillment`، RLS + اختبارات HTTP عابرة للمستأجرين، و3 اختبارات تزامن حقيقية محدَّدة بدقة). كل تعديل مُطبَّق حرفيًا أدناه.

---

## 1. القرار الأدق الذي احتاج فحصًا قبل التنفيذ: `StockReservation.reference`

طلبتَ صراحة عدم استخدام `reference=str(order.id)` قبل فحص semantics الحقل الحالي. الفحص: docstring الحقل في `apps/inventory/models.py` (Phase 5) ينص حرفيًا أنه *"caller-supplied and opaque -- no FK to Cart/Order... Inventory must not depend on them"*، وهو مُفهرَس فعليًا (`Index(["store", "reference"])`) — أي أن الحاجة لبحث متكرر "أعطني حجوزات هذا الطلب" **مُخطَّط لها ومُفهرَسة مسبقًا**، وليست فجوة تُرقَّع الآن. تبنّي علاقة FK حقيقية هنا كان سيجبر `apps.inventory` على استيراد `apps.orders`، **يعكس اتجاه الطبقات** الذي يفرضه import-linter منذ Phase 1 (الطبقات الدنيا لا تستورد العليا أبدًا). الخلاصة: هذه ليست حالة "علاقة domain دائمة تحتاج FK حقيقيًا" — إنه العكس، البقاء نصًّا معتمًا هو بالضبط ما صُمِّم له الحقل. اعتُمد العقد الصريح `f"order:{order.id}"` (`apps/orders/models.py:order_reservation_reference`)، وأُضيف عقد import-linter جديد يفرضه: `apps.inventory` لا تعتمد على `apps.orders`.

---

## 2. ما تم تنفيذه فعليًا

### apps.orders (تطبيق جديد)

**النماذج** (`Order`, `OrderItem`, `CheckoutSession`, `OrderNumberSequence`, `IdempotencyKey`) — كلها `TenantOwnedModel` قياسية، RLS كاملة، module docstring يوثّق 7 قرارات نطاق محدَّدة (Guest-only، snapshots غير قابلة للتغيير، semantics المجاميع، لا `billing_address`، لا `Shipment`، حالة `Order.status` الوحيدة `pending_payment`، عقد `reference`).

**تسلسل Checkout الحقيقي** عبر `POST storefront/checkout/{start,address,shipping,complete}`:
- `start`: يرفض سلة فارغة، يعيد استخدام جلسة نشطة قائمة بدل تكرارها (قيد DB جزئي: جلسة `active` واحدة فقط لكل Cart).
- `address`: JSONB مُتحقَّق منه بصرامة (serializer)، بلا `CustomerAddress`.
- `shipping`: يستدعي `apps.shipping.services.get_quotes_for_destination` **من جديد** (نفس محرّك Phase 7 بلا تعديل) للتحقّق الفوري، يخزّن الاختيار كـ**نيّة** فقط على `CheckoutSession`.
- `complete`: العملية الذرّية الوحيدة — تعيد كل شيء من الصفر (السعر الحالي لكل `ProductVariant`، صلاحية الكوبون، اقتباس شحن جديد بالكامل)، **لا تثق** بأي لقطة سابقة (لا `CartItem.unit_price_amount`، لا نيّة الشحن على الجلسة، لا `/cart/reprice`، لا فحص مخزون سابق).

**`checkout/payment` غير مبني عمدًا** (قرار نطاق صريح، لم يُطلَب تحديدًا لكن مُبرَّر): لا يوجد `PaymentProvider` بعد (Phase 9)، والقرار المعتمَد 12 يمنع أي COD/دفع في Phase 8. `complete` ينتقل مباشرة من `shipping` إلى إنشاء Order بحالة `pending_payment` — إضافة خطوة `payment` لاحقًا لا تحتاج لمس `start/address/shipping/complete`.

**Dashboard**: `GET .../orders` و`.../orders/{id}` — قراءة فقط (لا fulfill/cancel، خارج نطاق Phase 8 صراحةً).

### semantics المجاميع (مُحدَّدة ومُختبَرة صراحةً، كما طلبتَ)
```
subtotal_amount = Σ(unit_price_amount × quantity)   -- سعر Variant الحالي، ليس لقطة Cart
discount_amount = calculate_discount(subtotal, coupon)      -- apps.pricing.calculator، غير مُعدَّل
tax_amount      = calculate_tax(subtotal - discount, tax_rate)  -- الشحن مستبعد من الوعاء الضريبي
shipping_amount = اقتباس شحن سلطوي جديد بالكامل، غير خاضع للضريبة
total_amount    = (subtotal - discount) + tax + shipping_amount
```
`apps.pricing.calculator` يُستهلَك كما هو بلا تعديل — الشحن يُركَّب فوقه في `apps.orders.services`، لا محرّك تسعير رابع.

### Idempotency (DB-backed، كما نصّ `docs/ARCHITECTURE.md` §5.2)
`(store, key)` قيد تفرّد على `IdempotencyKey` هو الحد الفاصل الحقيقي، ليس Redis (لم يُستخدَم Redis إطلاقًا هنا — DB وحدها كافية وأبسط لهذا الحجم). نمط `try: INSERT / except IntegrityError: SELECT الموجود` يعمل بأمان تحت تزامن حقيقي لأن Postgres يحجب إدراجًا ثانيًا بنفس المفتاح حتى تُغلَق المعاملة الأولى — مُثبَت فعليًا (القسم 5). مفتاح مكرَّر لجلسة مختلفة (fingerprint مختلف) ⇒ 409، لا إعادة تشغيل صامتة.

---

## 3. RLS والعزل — مُختبَر فعليًا لكل الجداول الخمسة الجديدة

`Order`, `OrderItem`, `CheckoutSession`, `OrderNumberSequence`, `IdempotencyKey` — كلها `standard_tenant_policy_sql` القياسي. سُجِّلت في `apps/orders/tests/isolation_factories.py`، مجموعة العزل العامة صارت **141 اختبارًا** (كانت 116). بالإضافة، `apps/orders/tests/test_checkout_isolation.py` يثبت الخاصية عبر HTTP الحقيقي (وليس فقط عبر factory عام): توكن سلة صالح 100% لمتجر B، مُقدَّم لمتجر A، **لا** يكشف جلسة checkout متجر B — يُنشئ سلة A فارغة جديدة بدلًا من ذلك (نفس آلية Phase 6 المُثبَتة لـCart، مُمتَدة بشكل طبيعي لأن `CheckoutSession` تُحَل حصرًا عبر `self.cart`). كذلك اختبار HTTP عابر للمستأجرين لاسترجاع Order من لوحة متجر آخر (404، ليس 403 — نفس منطق كل الأسطح السابقة).

---

## 4. Concurrency — 5 invariants حقيقية، اتصالات PostgreSQL مستقلة حقيقية (3 من الاعتماد الأصلي + 2 من جولة المراجعة)

`apps/orders/tests/test_concurrency.py` — نفس النمط المُثبَت من Phase 5 (`app_migrator` للإعداد بـcommits حقيقية، `app_user` للتنافس الفعلي، بلا `transaction=True` لتفادي مشكلة صلاحية TRUNCATE):

1. **آخر وحدة مخزون، طلبان مختلفان**: وحدة واحدة متاحة، Order A وOrder B يتنافسان — واحد فقط ينجح، **صفر حجز يتيم للخاسر** (تحقَّق صراحة: `reservation_count == 1`)، تحت عقد `order:<uuid>` الجديد بالضبط.
2. **نفس Idempotency-Key بالتزامن**: طلبان متزامنان حقيقيان بنفس المفتاح — واحد `created`، الآخر `replayed` بنفس الاستجابة **حرفيًا**، صف واحد فقط في `orders_idempotencykey`.
3. **آخر استخدام كوبون**: `usage_limit=1, times_used=0`، طلبان متزامنان — واحد فقط يستهلكه (`times_used == 1` في النهاية، ليس 2).
4. **`OrderNumberSequence` (جديد، جولة المراجعة، نقطة 1)**: نفس Store، اتصالان مستقلان يتنافسان على نفس صف التسلسل بنفس تسلسل قفل `_next_order_number` الحقيقي — كلاهما ينجح، رقمان مختلفان `[1, 2]`، لا زيادة مفقودة، لا تكرار، **صفر `IntegrityError` متسرّب**، التسلسل ينتهي عند `2`.
5. **Single-order-per-CheckoutSession (جديد، جولة المراجعة، نقطة 2)**: طلبا `complete` متزامنان حقيقيان على **نفس** الجلسة بمفتاحي Idempotency **مختلفين** — واحد فقط `completed`، الآخر `rejected`، الحالة النهائية `completed` بلا ازدواج. هذا الاختبار يُثبت إصلاح race condition حقيقي (القسم 0.A.1 أعلاه)، وليس تأكيدًا لسلوك كان آمنًا أصلًا.

**5 تشغيلات متتالية إضافية** (6 إجمالاً) لكل الملف بعد إضافة الاختبارين الجديدين — لا flakiness. لا اختبارات تزامن مُصطنَعة خارج هذه الخمسة، تمشّيًا مع تعليماتك الصريحة في كلا الجولتين.

---

## 5. Bugs — bug إنتاجي حقيقي واحد (وُجِد وأُصلِح في جولة المراجعة)، وbug واحد في كود الاختبار

### Bug إنتاجي حقيقي: race condition في `checkout_complete` (جولة المراجعة، القسم 0.A.1)

مُفصَّل بالكامل في القسم 0.A.1 أعلاه: الحارس الأصلي لحالة `CheckoutSession` كان يفحص كائنًا **غير مُقفَل**، فطلبا `complete` متزامنان حقيقيان بمفتاحي Idempotency-Key **مختلفين** على نفس الجلسة كانا قادرين نظريًا على إنتاج طلبين ناجحين. أُصلِح الجذر بقفل `select_for_update()` حقيقي على `CheckoutSession` داخل نفس المعاملة، وأُثبِت الإصلاح باختبار تزامن حقيقي جديد (القسم 4، البند 5). هذا لم يظهر في أي اختبار سابق لأن كل الاختبارات السابقة لهذا المسار كانت **تسلسلية**، لا تُمثّل تزامنًا حقيقيًا.

### Bug في كود الاختبار نفسه (الجولة الأولى)

أثناء كتابة اختبار Idempotency للتزامن، ظهر خطأ حقيقي وغير بديهي في **كود الاختبار** (وليس في `apps.orders.services`): بعد `UniqueViolation` واستدعاء `conn.rollback()`، الاستعلام التالي (`SELECT` على الصف الموجود) كان يعيد **صفرًا من الصفوف** رغم وجود الصف فعليًا. السبب: `SELECT set_config('app.current_store_id', ..., true)` بـ`is_local=true` هو إعداد **محصور بالمعاملة** — و`rollback()` الحقيقي (وليس نقطة استرجاع/savepoint) يمسحه، فيُستأنَف الاستعلام التالي بلا سياق tenant إطلاقًا فتحجبه RLS بصمت. الإصلاح: إعادة `set_config` بعد كل `rollback()`. **هذا لا يمثّل bug في الكود الإنتاجي** لأن `checkout_complete` الحقيقي يستخدم `transaction.atomic()` متداخلة (تُصبح savepoint، لا معاملة كاملة) — واسترجاع savepoint لا يمسح إعدادات `set_config` التي سُبِقَت به (المضبوطة مرة واحدة عند بداية الطلب بواسطة middleware)؛ الفحص هذا وثّقناه صراحة في كود الاختبار حتى لا يُساء فهمه لاحقًا كإشارة لخطأ حقيقي.

خطآن إضافيان اكتُشفا وصُحِّحا فورًا أثناء كتابة الاختبارات (وليس في الكود الإنتاجي):
- اختبار المسار السعيد الأول نسي إعداد `StockLocation`/`StockBalance` فعليًا (لا يوجد "منتج غير مادي" معفى من تتبّع المخزون في هذا المشروع) — 409 صحيح تمامًا، لكن الاختبار كان يتوقّع 201 خطأً؛ صُحِّح بإضافة الإعداد المطلوب.
- `OrderItem.variant_options_snapshot` كاد يُخزَّن من `ProductVariant.option_signature` مباشرة — وهو مصفوفة UUIDs خام لأغراض قيد تفرّد الكتالوج فقط، **ليس** لقطة قابلة للقراءة لاحقًا (تُصبح بلا معنى إن حُذفت/عُدِّلت قيم الخيار لاحقًا، وهذا بالضبط ما يُفترَض أن تمنعه اللقطة). صُحِّح **قبل** أي تشغيل اختبار: دالة `_option_snapshot` تحوّل `VariantOptionValue` إلى `[{"option": "Color", "value": "Red"}, ...]` قابل للقراءة بشرًا، بمعزل عن أي تعديل مستقبلي على الكتالوج.

---

## 6. جميع الاختبارات ونتائجها

```
458 passed (3 تشغيلات متتالية مستقرة للمجموعة الكاملة)
```
- عزل tenant عام: 141 (كانت 116 + 25 جديدة لـ5 جداول orders)
- `test_checkout_flow.py`: 5 — تدفّق كامل E2E، رفض سلة فارغة، Idempotency-Key إلزامي، خطوات ناقصة، حجز مخزون فعلي تحت عقد `order:<uuid>`
- `test_checkout_validation.py`: 6 — طريقة شحن أُلغيت، منتج أُرشِف، **تغيّر سعر يُلتقَط بشكل صحيح (ليس خطأ)**، مخزون غير كافٍ، كوبون أصبح غير صالح، طريقة شحن غير موجودة في الاقتباسات الحالية
- `test_checkout_edge_cases.py`: 11 — كل حالات حافة الجلسة (منتهية الصلاحية عند كل خطوة، إعادة استخدام جلسة، خطوات بالترتيب الخطأ، سلة أُفرِغَت بين الشحن والإكمال، إكمال مرتين بمفاتيح مختلفة بعد النجاح **تسلسليًا** (404، خاصية أضعف من اختبار التزامن الحقيقي في القسم 4)، حالة PENDING عالقة دفاعية)
- `test_idempotency.py`: 2 — إعادة تشغيل حرفية، تعارض عبر جلسة مختلفة
- `test_order_totals_semantics.py`: 4 — المعادلة الدقيقة مع/بدون ضريبة/خصم/شحن، `line_total_amount`
- `test_dashboard_orders.py`: 5 — قائمة، تفاصيل، 404 لمعرّف غير موجود، 403 لغير عضو، 404 عابر للمستأجرين
- `test_checkout_isolation.py`: 2 — عزل CheckoutSession عبر HTTP حقيقي، توكن مزوَّر
- `test_concurrency.py`: 5 — الخمسة invariants الحقيقية (القسم 4؛ 3 من الاعتماد الأصلي + 2 من جولة المراجعة)

---

## 7. Coverage

```
98% إجمالاً (2385 عبارة، 58 غير مُغطاة -- كلها موروثة من مراحل سابقة، غير متعلقة بـPhase 8)
apps/orders/*  100% في كل ملف (models/serializers/services/views/urls) -- بما فيها كود الإصلاح الجديد
```

---

## 8. Quality Gates

| البوّابة | النتيجة |
|---|---|
| ruff | ✅ نظيف |
| black | ✅ نظيف |
| mypy | ✅ نظيف (18 ملفًا في orders، صفر أخطاء) |
| import-linter | ✅ 8 عقود، صفر مخالفات (عقد جديد: inventory لا تعتمد على orders؛ تحديث كل العقود القائمة) |
| bandit | ✅ صفر مشاكل |
| makemigrations --check | ✅ لا تغييرات مفقودة |
| pytest | ✅ 458/458، تغطية 98%، 3 تشغيلات متتالية مستقرة (+ 6 تشغيلات إضافية لملف التزامن وحده) |
| ضمان عزل قاعدة اختبار PostgreSQL | ✅ نشط طوال المرحلة، لم يُلمَس |

---

## 9. القرارات المعمارية الجديدة (امتدادًا للمقترح المعتمَد في القسم 0)

| القرار | السبب |
|---|---|
| `checkout/payment` غير مبني في Phase 8 | لا `PaymentProvider` بعد؛ `complete` ينتقل من `shipping` إلى `pending_payment` مباشرة، إضافة الخطوة لاحقًا غير كاسرة |
| `OrderNumberSequence` جدول مستقل داخل `apps.orders`، ليس حقلًا على `Store` | يبقي رقمنة الطلبات معزولة تمامًا عن `apps.stores`، بنفس انضباط قفل `StockBalance` (Phase 5) |
| لا `line_total_amount` مخزَّن على `OrderItem` | مُشتقّ حتميًا من `unit_price_amount × quantity` (كلاهما لقطة ثابتة) — تخزينه كان state زائدًا قابلًا للانحراف |
| `_option_snapshot` بشري القراءة، ليس `option_signature` الخام | يمنع لقطة تاريخية تفقد معناها إذا عُدِّل/حُذِف خيار كتالوج لاحقًا |
| موقع المخزون: أول موقع نشط **يكفي الكمية كاملة**، بترتيب `id` حتمي (UUIDv7) | طبّق تعديلك الإلزامي حرفيًا؛ لا `first active location` بلا شرط الكفاية؛ لا split allocation عبر مواقع |

---

## 10. ما تم اختباره فعليًا / ما لم يتم

**تم اختباره فعليًا**: كل تدفّق checkout عبر HTTP حقيقي ضد PostgreSQL، semantics المجاميع بالمعادلة الدقيقة، إعادة التحقّق السلطوي الكامل (سعر/مخزون/كوبون/شحن) عند `complete`، الخمسة invariants الحقيقية للتزامن (مخزون، كوبون، Idempotency، ترقيم الطلبات، وحيد-الطلب-لكل-جلسة)، عزل tenant (عام + HTTP + عابر للمستأجرين تحديدًا لـOrder retrieval وCheckoutSession)، سلوك Idempotency تحت تزامن حقيقي.

**لم يتم اختباره / خارج النطاق عمدًا**:
- لا `checkout/payment`، لا COD، لا انتقال إلى `confirmed` (Phase 9).
- لا `Shipment`/`Fulfillment` (يعتمد على Payment/Order lifecycle لاحق).
- لا تنظيف تلقائي لسلال/جلسات checkout منتهية الصلاحية (Celery beat) — `expires_at` مخزَّن ومُتحقَّق منه عند القراءة، لكن لا مهمة دورية تحذفها بعد.
- Cart لا يُفرَّغ تلقائيًا بعد نجاح Order (قرار واعٍ، ليس سهوًا — إعادة الطلب بنفس المحتويات لاحقًا سلوك مقبول، وتفريغ Cart يفتح قرارات دورة حياة (`Cart.status=abandoned`؟) لم تُطلَب).
- Docker غير مُختبَر فعليًا (مستمر منذ Phase 1).

---

## 11. Technical debt مؤجَّل عمدًا

| البند | لماذا |
|---|---|
| `checkout/payment` endpoint | ينتظر `PaymentProvider` الحقيقي (Phase 9) |
| تنظيف Celery لجلسات/سلال منتهية الصلاحية | لا مستهلك حقيقي بعد لقرار "متى تُعتبَر منتهية فعليًا للحذف" |
| تفريغ Cart بعد Order ناجح | قرار UX مؤجَّل، ليس قرار صحة بيانات |
| Cross-location split allocation | مؤجَّل صراحة حتى بنية Fulfillment الحقيقية (تعليمك المباشر، القسم 6 من المقترح) |
| اقتران الضريبة بالشحن، وTaxRate متعدد الولايات القضائية | لا يزال غير محسوم عمدًا (Phase 6/7/8 جميعها أكّدت هذا التأجيل) |

---

## المرحلة التالية (Phase 9 — Payments حسب خارطة الطريق)

بانتظار موافقتك الصريحة قبل البدء.
