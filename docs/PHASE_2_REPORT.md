# Phase 2 Report — Accounts & Auth

**التاريخ:** 2026-08-20
**الحالة:** ✅ مكتملة — كل بوّابات الجودة خضراء فعليًا (95/95 اختبار، تغطية 92.58%)، ضد PostgreSQL 18.6 حقيقي عبر WSL2 (نفس بيئة Phase 1، لم تتغيّر).

---

## 1. ما تم تنفيذه فعليًا

### 1.1 هوية Platform (`accounts.PlatformUser`)
- تسجيل (`POST /api/v1/auth/register`): يتحقق من تفرّد البريد، يطبّق `AUTH_PASSWORD_VALIDATORS` (طول أدنى 10، لا كلمات شائعة، لا أرقام فقط)، يُرسل بريد تحقق تلقائيًا، لا يُعيد أبدًا كلمة المرور/الهاش في الاستجابة.
- تسجيل الدخول (`POST /api/v1/auth/login`): يتحقق من بيانات الدخول، يرفض المستخدم غير النشط، **يقفل الحساب بعد 5 محاولات فاشلة** على مفتاح (email+IP) مجتمعين لمدة 15 دقيقة، ويصفّر العدّاد عند نجاح الدخول.
- تسجيل الخروج (`POST /api/v1/auth/logout`): يُدرج الـ refresh token الحالي في القائمة السوداء فورًا.
- إعادة تعيين كلمة المرور (`/password/reset`, `/password/reset/confirm`): **استجابة متطابقة بصرف النظر عن وجود البريد** (مقاومة user enumeration)، رمز مرّة واحدة مُخزَّن كـ SHA-256 hash فقط (لا نص صريح أبدًا)، صلاحية 30 دقيقة، **يُبطل كل الجلسات النشطة الأخرى فور نجاح إعادة التعيين**.
- التحقق من البريد (`/email/verify/resend`, `/email/verify/confirm`): رمز موقَّع بـ `TimestampSigner` (لا تخزين DB)، صلاحية 24 ساعة، يرفض التلاعب والتوقيع الخاطئ.
- `GET /api/v1/auth/me`: هوية المستخدم الحالي فقط — **بدون** قائمة العضويات عبر المتاجر (قرار نطاق موثّق أدناه في §4).

### 1.2 JWT بعالَم Platform (`aud: "platform"`)
- Access 15 دقيقة / Refresh 30 يومًا، دوران (rotation) عند كل تحديث.
- **لا صلاحيات أو أدوار داخل التوكن إطلاقًا** — تحقّقتُ باختبار صريح أن `role`/`permissions`/`is_platform_staff`/`memberships` غائبة عن الـ payload.
- `PlatformJWTAuthentication` يرفض أي توكن لا يحمل `aud=platform` (يحمي من عالَم Customer/Storefront المستقبلي).
- **كشف إعادة استخدام (reuse detection) + إبطال العائلة الكاملة**: استخدام refresh token بعد دورانه لا يُرفض فقط هو، بل يُبطل **كل** التوكنات النشطة لذلك المستخدم — مُثبَت باختبار: توكن ثانٍ صالح تمامًا يصبح مرفوضًا بعد اكتشاف إعادة استخدام لتوكن آخر لنفس المستخدم، بينما مستخدم آخر غير متأثر إطلاقًا.

### 1.3 RBAC حقيقي (`accounts.StoreMembership`) — أول اختبار حقيقي لإطار Phase 1
`StoreMembership` هو أول نموذج نطاقي حقيقي (غير `StoreDomain`) يُبنى فوق `TenantOwnedModel` — أُضيف تلقائيًا لمجموعة اختبارات العزل التنانتي العامة من Phase 1 (5 اختبارات بارامترية جديدة: قراءة/تعديل/حذف/إدراج-مخالف/الطبقة السهلة) **دون أي تعديل** على تلك المجموعة — إثبات عملي أن الإطار يعمم بشكل صحيح.
- 5 أدوار ثابتة (owner/admin/manager/staff/viewer) + `extra_permissions` قابلة للتخصيص لكل عضوية.
- `resolve_permissions`/`has_permission`: دوال نقية مختبرة بالكامل (owner=wildcard، حالة removed/invited=صفر صلاحيات دائمًا حتى لو owner، الصلاحيات الإضافية تراكمية).
- RLS مُفعّلة فعليًا عبر `standard_tenant_policy_sql` من Phase 1 (أول استخدام حقيقي له).
- قيد فريد `(store, user)` — مُتحقَّق باختبار `IntegrityError`.

---

## 2. الاختبارات التي شُغِّلت فعليًا ونتائجها

```
95 passed in ~7s   (ضد PostgreSQL 18.6 حقيقي، لا SQLite ولا mocking لسلوك RLS/DB)
Coverage: 92.58% على apps/ (بوّابة 80% محقَّقة بفارق كبير)
```

ملفات اختبار Phase 2 الجديدة (50 اختبارًا): `test_permissions_catalog`، `test_registration`، `test_login` (شامل قفل brute-force)، `test_jwt_refresh` (دوران + إعادة استخدام + إبطال العائلة + عزل بين المستخدمين)، `test_logout`، `test_password_reset` (10 اختبارات تشمل anti-enumeration وinvalidate-all-sessions)، `test_email_verification`، `test_me_and_auth_boundary` (توكن منتهٍ، توكن مُلاعَب به، توكن من عالَم خاطئ)، `test_store_membership`.

كل بوّابات الجودة شُغِّلت فعليًا في هذه الجلسة (ليست افتراضًا):
```
ruff check .                 → All checks passed
black --check .              → 72 files unchanged
mypy apps config             → Success: no issues found in 68 source files
lint-imports --config ...    → 2 contracts kept, 0 broken
bandit -r apps config ...    → 0 issues
makemigrations --check       → No changes detected
manage.py check              → System check identified no issues
```

---

## 3. Bugs حقيقية اكتُشفت وكيف أُصلحت (لا إخفاء)

1. **Circular import عند الإقلاع**: `apps.tenancy.models` كان يستورد `TenantContextMissingError` من `apps.core.exceptions`، وهذا الملف يستورد DRF (`rest_framework.views`) على مستوى الوحدة، والذي بدوره (عبر `rest_framework.schemas`) يحلّ `DEFAULT_AUTHENTICATION_CLASSES` بشكل متلهّف عند وقت الاستيراد — وهذا الإعداد يشير الآن إلى `apps.accounts.tokens.PlatformJWTAuthentication`، ما يجبر Django على تحميل `apps.accounts.models` بينما `apps.tenancy.models` لا يزال في منتصف تحميله، فيفشل الاستيراد الدائري.
   **الإصلاح الجذري:** نقل `TenantContextMissingError` إلى `apps/tenancy/exceptions.py` جديد بلا أي اعتماد على DRF، بدل تفاف حول العرَض.
2. **قفل تسجيل الدخول لم يكن يعمل فعليًا**: عند فشل الدخول، `TokenObtainPairView.post()` يرفع استثناء (`AuthenticationFailed`) بدل إرجاع استجابة — فالكود بعد `super().post()` في `LoginView` لم يكن يُنفَّذ أبدًا عند الفشل، فعدّاد المحاولات الفاشلة لم يتزايد إطلاقًا. اكتُشف هذا عبر اختبار حقيقي فشل (`429 != 200`)، وليس افتراضًا.
   **الإصلاح:** لفّ `super().post()` بـ `try/except`، تسجيل الفشل في `except` ثم إعادة رفع الاستثناء.
3. **مفتاح توقيع JWT كان يتجاهل تخصيص كل بيئة**: `SIMPLE_JWT["SIGNING_KEY"]` في `base.py` كان يلتقط قيمة `SECRET_KEY` **وقت بناء القاموس في base.py نفسه** — إعادة تعيين `SECRET_KEY` لاحقًا في `test.py`/`production.py` لا تنعكس على هذا القاموس (نسخة نصية جامدة، لا مرجع حيّ). ظهر كتحذير `InsecureKeyLengthWarning` غريب أثناء الاختبارات، وتتبّعه كشف أن بيئة test تستخدم فعليًا مفتاح base.py الافتراضي بدل مفتاحها الخاص.
   **الإصلاح الجذري:** حذف `SIGNING_KEY` من `SIMPLE_JWT` كليًا، وترك simplejwt يستخدم افتراضه الخاص (`settings.SECRET_KEY`، يُحلّ بشكل كسول بعد اكتمال تحميل ملف الإعدادات الفعلي).
4. **mypy**: عدة مشاكل فعلية (ليست تجميلية) — `timezone.timedelta` غير مُصدَّر رسميًا من django-stubs (استُبدل بـ `datetime.timedelta` المباشر)، وعدم تطابق نوع `Request.user` (`PlatformUser | AnonymousUser`) — أُصلح بفحص `isinstance` صريح بدل `assert` (الذي رفعه bandit أيضًا كمشكلة B101 لأن `assert` يُحذف تحت `-O`).

---

## 4. قرارات معمارية جديدة (موثَّقة، لم تتطلب توقّفًا لأنها قابلة للعكس)

1. **`StoreMembership.role` enum ثابت (5 أدوار) بدل جدول `Role` قابل للتخصيص لكل متجر.** لا يوجد أي app نطاقي بعد (catalog/orders) يحتاج صلاحيات دقيقة تبرر جدولاً منفصلاً؛ `extra_permissions` يغطي "صلاحيات الموظف قابلة للتخصيص" من المتطلبات الأصلية دون بناء نظام أدوار كامل مبكرًا جدًا. **قابل للعكس بسهولة لاحقًا** (إضافة جدول `Role` لا يكسر `StoreMembership` الحالي).
2. **`/auth/me` لا يُرجع قائمة عضويات المستخدم عبر المتاجر.** هذا استعلام عابر للمتاجر بطبيعته، ولا يمكن تنفيذه بأمان عبر RLS الحالية (GUC واحدة خاصة بـ tenant فقط) دون أحد حلّين: (أ) بُعد GUC ثانٍ (`app.current_user_id`) بسياسة RLS إضافية على `StoreMembership`، أو (ب) دور DB منفصل bypass للقراءات العابرة للمتاجر (`app_platform`، مؤجَّل أصلاً لـ platform_admin). **قرّرتُ عدم الالتزام بأيٍّ منهما الآن** وتأجيل الميزة كاملة — قرار متحفّظ وقابل للعكس (لا يمنع أيًّا من الخيارين لاحقًا)، فلم يستدعِ توقّفًا لأخذ رأيك بحسب معيارك ("قرار يصعب التراجع عنه").
3. **قفل brute-force بكاش بسيط بدل `django-axes` الكامل.** حماية حقيقية ومُختبرة (5 محاولات/15 دقيقة على email+IP)، لكن أقل غنى من `django-axes` (لا لوحة إدارية، لا نطاقات IP). مؤجَّل التكامل الكامل لـ Phase 17 (Security Hardening) كما هو مخطَّط أصلاً في خارطة الطريق.

---

## 5. قيود/أجزاء لم يتم التحقق منها

- **Docker لا يزال غير مُختبَر فعليًا** (نفس قيد Phase 1، لم يتغيّر — لا تعتبره Production-verified).
- لا اختبار فعلي لإرسال بريد SMTP حقيقي (console/locmem فقط، كما هو مخطَّط — الإنتاج يستخدم SMTP عبر `production.py`).
- `django-axes` الكامل غير مُطبَّق (مؤجَّل، انظر §4.3).
- لا نقطة HTTP فعلية لدعوة موظف لمتجر (`StoreMembership` يُختبر عبر ORM فقط الآن) — منطقي لأن إنشاء المتجر نفسه لم يُبنَ بعد (Phase 3).
- نقطتا `_tenant/context` و`_debug` من Phase 1 لا تزالان موجودتين ومؤقّتتين كما كانتا — لم تُحذفا بعد لأن نقاط dashboard الحقيقية لم تصل بعد.

---

## 6. الحالة النهائية لكل quality gates

| البوّابة | النتيجة |
|---|---|
| ruff | ✅ نظيف |
| black | ✅ نظيف |
| mypy | ✅ نظيف (68 ملف) |
| import-linter | ✅ عقدان، صفر مخالفات (استثناء اختباري واحد موثَّق لا يُضعف الإنتاج) |
| bandit | ✅ صفر مشاكل |
| makemigrations --check | ✅ لا تغييرات مفقودة |
| manage.py check | ✅ لا مشاكل |
| pytest | ✅ 95/95، تغطية 92.58% (بوّابة 80%) |

---

## المرحلة التالية (Phase 3 — Store Creation)

بانتظار موافقتك الصريحة قبل البدء.
