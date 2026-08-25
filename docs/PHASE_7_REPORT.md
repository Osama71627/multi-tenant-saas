# Phase 7 Report — Shipping

**التاريخ:** 2026-08-22
**الحالة:** ✅ مكتملة — 392/392 اختبار ناجح فعليًا ضد PostgreSQL حقيقي (كانت 342 في نهاية Phase 6 + 50 اختبارًا جديدًا لهذه المرحلة)، تغطية 97% إجمالاً و100% لكل ملفات `apps.shipping`، كل بوّابات الجودة خضراء. DoD الرسمي لخارطة الطريق ("quotes صحيحة لكل الحالات") محقَّق ومُختبَر صراحةً لكل الأنواع الخمسة.

---

## 0. مطابقة `docs/ARCHITECTURE.md` قسم 9 — تم التحقق قبل وأثناء التنفيذ

قرأتُ القسم 9 ("Shipping Architecture") وسطر Phase 7 في جدول خارطة الطريق (القسم الأخير) قبل الكتابة، كما طُلب صراحةً. المطابقة:

| ما ينص عليه المخطَّط | ما بُني |
|---|---|
| `ShippingZone(store, name, countries[], regions[], postal_patterns[])` | مطابق حرفيًا + `priority`/`is_active` (تفاصيل تنفيذ عكوسة) |
| `ShippingMethod(zone, name, kind, is_active)` | مطابق + `position` (ترتيب عرض، عكوس) |
| `ShippingRate(method, min_value, max_value, price_amount)` | مطابق + `currency` (إلزامي حسب اتفاقية المشروع للمال، القسم 6) |
| `CarrierProvider` ABC: `get_rates/create_shipment/track/cancel` + `MockCarrier` فقط في v1 | مطابق حرفيًا — 4 methods بالضبط، `MockCarrier` بتسعير حتمي مرتبط بالوزن |
| محرّك تسعير نقي `(cart, address, config) → [RateOption]` بلا DB | مطابق — `apps/shipping/calculator.py` دالة واحدة نقية، صفر استعلامات |
| DoD خارطة الطريق (صف 7): "مناطق/طرق/أسعار + تجريد الناقل → quotes صحيحة لكل الحالات" | محقَّق — كل الأنواع الخمسة (`flat/free/weight_based/price_based/carrier_calculated`) مُختبَرة صراحةً بما فيها حالات "لا سعر صالح" |
| `Shipment(order, fulfillment, carrier, tracking_number, status, ...)` | **لم يُبنَ عمدًا** — يعتمد على `order` غير الموجود بعد؛ خارطة الطريق نفسها لا تذكر `Shipment` ضمن تسليم Phase 7 (تذكره فقط في تخطيط القسم 9 العام). سيُبنى مع Phase 8 (Checkout & Orders) |
| "الأسعار المحسوبة من شركة الشحن تُخزَّن مؤقتًا في Redis (TTL قصير)" | **لم يُنفَّذ** — انحراف حقيقي عن تفصيل معماري مذكور، وليس عن DoD الرسمي. مُسجَّل صراحةً في القسم 6 (Technical debt) أدناه — ليس إغفالًا صامتًا |

---

## 1. قرارات نطاق اتُّخذت كتفاصيل تنفيذ عكوسة (بدون طلب موافقة مسبقة) — معروضة الآن للمراجعة

طبقًا لتفويضك: "تفاصيل التنفيذ العكوسة لا تحتاج موافقة." اتخذتُ 4 قرارات ضمن هذا التصنيف أثناء البناء. أعرضها الآن بوضوح ليكون لك حق الاعتراض:

1. **لا `Shipment` في هذه المرحلة** — يعتمد بنيويًا على `Order` (Phase 8). بناؤه الآن يعني إما جدولًا بلا استهلاك حقيقي أو ربطًا مؤقتًا سيُعاد كتابته بالكامل لاحقًا. عكوس بالكامل: `Shipment` سيُضاف كجدول جديد في Phase 8، لا حاجة لتعديل أي شيء هنا.
2. **لا حقل `Cart.shipping_method` ولا اختيار شحن مُخزَّن على السلة** — يمنع بالضبط الفخ الذي حذّرتَ منه في اعتماد Phase 6: أن يصبح `/cart/reprice`-مثيل شحن نقطة ثقة ضمنية قبل الدفع. الوجهة (`country_code`/`region`/`postal_code`) تُمرَّر مباشرة في طلب quote، وليست مملوكة لأي نموذج مخزَّن (لا يوجد `apps.customers`/`Address` بعد).
3. **مطابقة المنطقة (zone) بالأولوية، أول تطابق يفوز** — `ShippingZone.priority` (الأصغر = أعلى أولوية)، مطابقة لنمط `Meta.ordering` المستخدَم سابقًا في `apps.catalog`/`apps.pricing`. وجهة واحدة تنتمي لمنطقة واحدة فقط أبدًا، لا دمج.
4. **اقتران الضريبة بالشحن مؤجَّل صراحةً وغير محسوم هنا** — نفس التحذير الذي أبديتَه أنت عن `TaxRate` في اعتماد Phase 6 ("لا تفترض أن Store → معدّل ضريبة واحد سيبقى دائمًا"). محرّك الشحن هنا لا يعرف شيئًا عن الضرائب؛ عندما تحتاج خارطة الطريق نمطًا حقيقيًا لضريبة-على-شحن، سيُعرَض كخيارات قبل أي قرار.

---

## 2. ما تم تنفيذه فعليًا

### apps.shipping (تطبيق جديد، store-scoped بالكامل)
- `ShippingZone`: مطابقة الدولة (قائمة فارغة = catch-all)، المنطقة، وبادئة الرمز البريدي (`postal_patterns` — مطابقة **بادئة** لا مطابقة كاملة، مُختبَرة صراحةً).
- `ShippingMethod`: 5 أنواع (`flat/free/weight_based/price_based/carrier_calculated`).
- `ShippingRate`: قيد DB (`CheckConstraint`) يمنع `max_value < min_value` على مستوى قاعدة البيانات، لا فقط تحقّق تطبيقي.
- `apps/shipping/calculator.py`: `compute_method_price` — دالة نقية بلا DB، `None` يعني صراحة "لا سعر صالح لهذه المُدخلات" (تُستبعَد الطريقة من النتائج، لا تُسعَّر صفرًا بصمت أبدًا).
- `apps/shipping/carriers.py`: `CarrierProvider` (ABC) + `MockCarrier` — تسعير حتمي مرتبط بالوزن (تقسيم صحيح بلا floats)، `create_shipment/track/cancel` تُطلِق `NotImplementedError` عمدًا (تُبنى مع Phase 8+) — سلوك مُختبَر صراحةً، وليس فجوة تغطية مسكوتًا عنها.
- `apps/shipping/services.py`: `find_matching_zone` (أولوية)، `total_weight_grams`، `get_quotes_for_destination` (الأورشستريشن الوحيد الذي يلمس DB).
- واجهات Dashboard: `GET/POST .../shipping/zones`، `.../zones/<id>/methods`، `.../methods/<id>/rates` — 404 مقابل 403 بنفس منطق الأنماط السابقة (Phase 3/4).

### apps.carts — أول مستهلك حقيقي لـ apps.shipping
- `GET /api/v1/storefront/cart/shipping-quotes?country_code=...` — **معلوماتي فقط**، لا يُخزِّن شيئًا على السلة، لا يصبح شرطًا مسبقًا للدفع (القرار 2 أعلاه، ونفس القاعدة الإلزامية التي وضعتَها لـPhase 8 بخصوص `/cart/reprice`).
- إضافة عقد import-linter جديد: `apps.shipping` لا تعتمد على `apps.carts/pricing/inventory` — الاتجاه المسموح هو `carts → shipping` فقط، أبدًا العكس (تحقَّق فعليًا: 8 عقود، صفر مخالفات).

---

## 3. RLS والعزل — مُختبَر فعليًا لكل جدول جديد

الثلاثة جداول الجديدة (`shipping_shippingzone`, `shipping_shippingmethod`, `shipping_shippingrate`) تستخدم `standard_tenant_policy_sql` القياسي (نفس إصلاح `NULLIF` من Phase 1/4). سُجِّلت في `apps/shipping/tests/isolation_factories.py` وأُدرِجت في `backend/tests/test_tenant_isolation.py` — مجموعة العزل العامة صارت **116 اختبارًا** (كانت مطبَّقة تلقائيًا على كل `TenantOwnedModel` مسجَّل، ونجحت كاملة).

---

## 4. Concurrency — لا اختبار تزامن مخصَّص لهذه المرحلة، والسبب محدَّد

لا يوجد في `apps.shipping` أي مورد نادر مُتنازَع عليه بين طلبات متزامنة (لا عدّاد مشترك، لا حجز، لا قيد تفرّد يعتمد على قراءة-ثم-كتابة). `ShippingRate`'s `CheckConstraint` هو قيد على صف واحد يُفرَض ذريًّا بواسطة PostgreSQL نفسه بغض النظر عن التزامن. تمشّيًا مع قاعدتك الصريحة ("لا تصنع اختبارات تزامن بلا invariant حقيقي") — لم يُضَف اختبار تزامن مصطنَع.

---

## 5. جميع الاختبارات ونتائجها

```
392 passed (كانت 342 في نهاية Phase 6؛ +50 اختبارًا جديدًا)
```

- `test_tenant_isolation.py` (عام): 116 (كانت 106 + 10 جديدة لجداول shipping الثلاثة)
- `apps/shipping/tests/test_calculator.py`: 12 — كل الأنواع الخمسة (بما فيها حالات "لا سعر صالح")، تسعير `MockCarrier` الحتمي، تأكيد صريح أن `create_shipment/track/cancel` تُطلِق `NotImplementedError`
- `apps/shipping/tests/test_zone_matching.py`: 5 — منطقة catch-all، تقييد الدولة، تقييد المنطقة، مطابقة بادئة الرمز البريدي، حالة عدم وجود رمز بريدي
- `apps/shipping/tests/test_services.py`: 7 — أولوية المناطق، لا تطابق، دمج طرق متعددة، استبعاد طريقة بلا سعر صالح، حقن ناقل مخصَّص، حساب الوزن الإجمالي
- `apps/shipping/tests/test_views.py`: 10 — CRUD كامل، 404 لأب غير موجود (على مستويي method وrate)، رفض قيد `max<min`، منع غير الأعضاء (403)
- `apps/carts/tests/test_shipping_quotes.py`: 5 — سلة فارغة، سلة بعناصر، لا منطقة مطابقة، رفض بلا `country_code`، **إثبات صريح أن الاستدعاء لا يُخزِّن أي شيء على السلة**

---

## 6. Coverage

```
97% إجمالاً (2027 عبارة، 59 غير مُغطاة)
apps/shipping/*  100% في كل ملف (calculator/carriers/models/serializers/services/urls/views)
apps/carts/views.py  96% (الفجوة المتبقية 72-73/79-80 موروثة من Phase 6، غير متعلقة بهذه المرحلة)
```

---

## 7. Quality Gates

| البوّابة | النتيجة |
|---|---|
| ruff | ✅ نظيف |
| black | ✅ نظيف |
| mypy | ✅ نظيف (33 ملفًا في shipping/carts، لا أخطاء) |
| import-linter | ✅ 8 عقود، صفر مخالفات (عقد جديد لـshipping + تحديث 6 عقود قائمة) |
| bandit | ✅ صفر مشاكل |
| makemigrations --check | ✅ لا تغييرات مفقودة |
| pytest | ✅ 392/392، تغطية 97% |
| ضمان عزل قاعدة اختبار PostgreSQL (`backend/conftest.py`) | ✅ نشط طوال هذه المرحلة (لم يُعطَّل ولم يُلمَس) — كل تشغيلات pytest أعلاه مرّت من خلاله دون توقّف الجلسة |

---

## 8. Bugs — لا يوجد bug إنتاجي أثناء هذه المرحلة

لم يظهر أي خطأ إنتاجي جوهري. الفجوات الوحيدة التي ظهرت كانت في تغطية الاختبارات نفسها أثناء الكتابة (فرعا 404 غير مُختبَرين ابتداءً في `_get_method_or_404` عبر مسارين مختلفين) — أُضيف اختباران (`test_rate_under_unknown_method_is_404`, `test_list_rates_under_a_method`) لسدّهما فورًا، لا كـpatch لاحق.

---

## 9. Technical debt مؤجَّل عمدًا

| البند | لماذا |
|---|---|
| تخزين مؤقت لأسعار `carrier_calculated` في Redis (مذكور صراحة في القسم 9) | `MockCarrier` الحالي حتمي وفوري، فلا حاجة فعلية لكاش الآن؛ سيُضاف كطبقة تحسين عكوسة بلا تعديل مخطَّط عندما يُربَط ناقل حقيقي (SMSA/Aramex/DHL) بزمن استجابة حقيقي |
| `Shipment` (تتبّع تنفيذ الطلب) | يعتمد على `Order` — Phase 8 |
| اقتران الضريبة بالشحن | غير محسوم عمدًا (القرار 4 أعلاه) — سيُعرَض كخيارات عند الحاجة |
| ربط اختيار شحن فعلي بالطلب عند الدفع | ينتظر Phase 8؛ نقطة `/cart/shipping-quotes` الحالية معلوماتية بحتة تمامًا كما هو مخطَّط |

---

## المرحلة التالية (Phase 8 — Checkout & Orders حسب خارطة الطريق)

بانتظار موافقتك الصريحة قبل البدء، بما في ذلك مراجعتك للقرارات الأربعة في القسم 1 أعلاه إن رغبت بالاعتراض على أي منها.

---

## 10. Addendum (بعد الاعتماد) — Deterministic tie-break لتساوي `priority`

عند اعتماد Phase 7 طلبتَ التأكد من وجود deterministic tie-breaker عند تساوي `priority` بين منطقتين، حتى لا يُعتمَد على ترتيب PostgreSQL غير المحدَّد. تم التحقّق: **كان موجودًا فعليًا من البداية** — `ShippingZone.Meta.ordering = ["priority", "id"]` (apps/shipping/models.py)، و`id` هو UUIDv7 فريد عالميًا وقابل للترتيب زمنيًا، فلا يتساوى أبدًا بين صفّين. `find_matching_zone` (apps/shipping/services.py) لا يتجاوز هذا الترتيب الافتراضي.

أُضيف اختبار صريح يثبت هذا بدلاً من مجرد الافتراض: `test_find_matching_zone_tie_break_on_equal_priority_is_deterministic` (apps/shipping/tests/test_services.py) — ينشئ منطقتين بنفس `priority`، ويؤكّد أن `find_matching_zone` يعيد نفس المنطقة (الأقدم `id`) في كل استدعاء.

**النتيجة بعد الإضافة:** 393/393 اختبار ناجح، كل بوّابات الجودة (ruff/black/mypy/import-linter/bandit) نظيفة.
