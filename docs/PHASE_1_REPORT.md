# Phase 1 Report — Bootstrap + Core + Tenancy Foundation

**التاريخ:** 2026-08-20
**الحالة:** ✅ مكتملة — كل بوّابات الجودة خضراء، وكل الاختبارات تعمل فعليًا مقابل PostgreSQL 18.6 حقيقي.

---

## 1. ما تم بناؤه

### 1.1 حسم القرارات المعمارية المفتوحة (قبل أي كود)
- **UUIDv7**: تحقّقتُ فعليًا (بحث حيّ + اختبار على الجهاز) أن `uuid.uuid7()` في stdlib موجودة فقط من Python 3.14، وأن `uuidv7()` الأصلية في PostgreSQL موجودة فقط من إصدار 18. تجنّبتُ الاعتماد على كليهما وعلى أي مكتبة خارجية — بنيتُ مولّدًا خاصًا بنا (`apps/core/uuid7.py`) متوافقًا مع RFC 9562، بدون أي تبعية، ومغطّى باختبارات (تفرّد، ترتيب زمني، أمان تزامن الخيوط).
- **بيئة التشغيل المثبَّتة**: Python 3.12.10، Django 5.2.17 LTS، PostgreSQL 18.6، Redis 7 — تم التحقّق من كل هذه الإصدارات فعليًا (ليست افتراضات).

### 1.2 البنية التحتية للتطوير
- لا يوجد Docker مثبَّت على جهاز التطوير (تحقّقتُ: `docker --version` فشل، لا عملية تستمع). بموافقتك استخدمتُ **WSL2 (Ubuntu-22.04)** لتشغيل PostgreSQL 18.6 و Redis 7 فعليًا محليًا، على منافذ غير افتراضية (15432 و16379) لتفادي تعارضٍ مع نسخة Postgres أخرى موجودة مسبقًا على Windows نفسه على المنفذين 5432 و5433 (اكتُشف ذلك أثناء التصحيح ووُثّق).
- `docker-compose.yml` و`backend/Dockerfile` و`infra/postgres/init/01-roles.sh` مكتوبة بنفس مستوى الجودة، **لكن لم تُنفَّذ فعليًا في هذه الجلسة** (لا Docker). صرّحتُ بذلك بوضوح في `README.md` و`docker-compose.yml` نفسه — يُرجى تجربة `docker compose up --build` والإبلاغ عن أي مشكلة.

### 1.3 Multi-Tenancy الحقيقي (Shared Schema + `store_id` + PostgreSQL RLS)
- **دوران قاعدة بيانات منفصلان**، تم إنشاؤهما والتحقّق منهما فعليًا:
  - `app_migrator`: `CREATEDB`، ليس superuser، يملك الجداول، يُستخدم فقط عبر `manage.py migrate --database=migrator`.
  - `app_user`: `NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS` — هو ما يتصل به التطبيق فعليًا (`DATABASES["default"]`). تحقّقتُ عبر استعلام مباشر على `pg_roles` أن هذه الصلاحيات صحيحة، وأن هذا الدور لا يملك أي جدول تنانتي.
  - `DATABASE_ROUTERS` (`apps/tenancy/routers.py`) يجعل `python manage.py migrate` العادي (بدون `--database=migrator`) **no-op آمنًا** بدل خطأ صلاحيات مربك.
- **RLS مُفعّلة فعليًا** على `stores_store` و`stores_storedomain` (تحقّق مباشر من `pg_class.relrowsecurity`)، بسياسات صريحة موثّقة في الترحيل نفسه.
- **`SET LOCAL` آمن**: استخدمتُ `SELECT set_config('app.current_store_id', %s, true)` مع bind parameter حقيقي — **ليس** `SET LOCAL ... = 'قيمة مُدرَجة بالنص`، الذي كان سيفتح بابًا نظريًا لحقن SQL. `is_local=true` يجعل القيمة محصورة داخل transaction واحدة فقط — متوافقة مع pgbouncer في وضع transaction pooling ومع اتصالات Django الدائمة (`CONN_MAX_AGE`) دون تسرّب بين الطلبات.
- **`TenantMiddleware`** (`apps/stores/middleware.py`) يفتح transaction واحدة تُغلّف الطلب بأكمله، ويضبط الـ GUC **دائمًا** — حتى لقيمة "لا يوجد tenant" — لمنع أي تسرّب عبر اتصال مُعاد استخدامه. الحل الأول (وضع الـ transaction في `ATOMIC_REQUESTS`) كان خاطئًا لأن Django يُغلّف الـ view فقط وليس الـ middleware؛ صُحِّح واختُبر.
- **`TenantOwnedModel` + `TenantManager` + `UnscopedManager`** (`apps/tenancy/models.py`): القراءات الافتراضية (`Model.objects`) تفشل بأمان (fail-closed) إن لم يوجد tenant context، بدل إرجاع بيانات غير مُصفّاة.
- **`TenantTask`/`PlatformTask`** (`apps/tenancy/celery.py`): مهام Celery يجب أن تُرسَل عبر `dispatch_for_store(task, store_id, ...)` صراحةً؛ أي محاولة `.delay()`/`.apply_async()` مباشرة بلا `store_id` تفشل عند الإرسال (`TypeError`)، لا داخل المهمة.
- **استثناء موثّق واحد فقط**: `StoreDomain` لديها سياسة `SELECT` مفتوحة (`USING (true)`) لأن حلّ اسم النطاق إلى Store يجب أن يعمل *قبل* معرفة أي tenant — النطاقات معلومة عامة أصلاً (كـ DNS). كل الكتابة عليها تبقى مقيّدة بالكامل. هذا الاستثناء مُسجَّل صراحةً في نظام الاختبار (`select_is_open=True`) لا مخفيًا.

### 1.4 نموذج مستخدم أدنى (`accounts.PlatformUser`)
أُنشئ الآن (لا في Phase 2) لأن تبديل `AUTH_USER_MODEL` بعد أول `migrate` مؤلم جدًا في Django. لا تدفّقات تسجيل/دخول/JWT فعلية بعد — تلك تبقى Phase 2 كما هو مخطَّط.

---

## 2. الملفات المهمة

```
backend/config/settings/{base,local,test,production}.py   إعدادات مفصولة، fail-fast في production
backend/apps/core/uuid7.py                                 مولّد UUIDv7 الخاص بنا (RFC 9562)
backend/apps/core/models.py                                BaseModel, TimeStampedModel, EventLog
backend/apps/core/logging.py                                JSON logging + تنقية الأسرار تلقائيًا
backend/apps/tenancy/context.py                             ContextVar آمن لـ async/threads
backend/apps/tenancy/db.py                                   جسر Python → GUC آمن (set_config)
backend/apps/tenancy/models.py                               TenantOwnedModel + Managers
backend/apps/tenancy/celery.py                                TenantTask/PlatformTask
backend/apps/tenancy/rls.py                                   قالب SQL لسياسات RLS القياسية (لمراحل لاحقة)
backend/apps/tenancy/privileges.py                             منح صلاحيات app_user تلقائيًا بعد كل migrate
backend/apps/tenancy/routers.py                                يمنع migrate عبر app_user
backend/apps/stores/models.py                                  Store (الجذر) + StoreDomain
backend/apps/stores/middleware.py                               TenantMiddleware (يعيش هنا، لا في tenancy — راجع القرار المعماري أدناه)
backend/apps/accounts/models.py                                 PlatformUser الأدنى
backend/tests/test_tenant_isolation.py                          ⭐ حزمة العزل التنانتي العامة والتلقائية
docker-compose.yml, backend/Dockerfile, infra/postgres/init/01-roles.sh
.github/workflows/ci.yml
```

### قرار معماري وُلد أثناء التنفيذ (يستحق التوثيق)
خططتُ أصلًا لوضع `TenantMiddleware` داخل `apps.tenancy`. لكن `import-linter` (الذي يفرض القاعدة: `apps.tenancy` يجب ألا يعتمد على أي app نطاقي) رفض ذلك فعليًا — لأن حلّ "أي متجر هذا الطلب" يتطلب معرفة نموذجَي `Store`/`StoreDomain` بالضرورة. الحل الصحيح المعماري، وليس مجرد إسكات الأداة: نقلتُ `TenantMiddleware` إلى `apps.stores` (وهو app نطاقي يُسمح له بالاعتماد على `apps.tenancy`)، وأبقيتُ `apps.tenancy` آلية عامة صرفة بلا أي استيراد من apps نطاقية. `import-linter` الآن **يمرّ فعليًا لا شكليًا**.

---

## 3. Database Migrations

```
accounts.0001_initial   → PlatformUser
core.0001_initial       → EventLog
stores.0001_initial     → Store, StoreDomain + سياسات RLS (RunSQL) + عكسها (reverse_sql)
```
كلها مُطبَّقة فعليًا عبر `--database=migrator` وتم التحقّق من `pg_class`/`pg_policies`/`information_schema.role_table_grants` مباشرة (ليس افتراضًا).

---

## 4. API Endpoints

لا توجد نقاط API إنتاجية بعد — هذا مقصود، الأسطح الأربعة (auth/platform/dashboard/storefront) تبدأ Phase 2+. يوجد فقط:
- `GET /healthz` — فحص حيوية بلا لمس قاعدة البيانات.
- `GET /api/schema/`, `/api/docs/`, `/api/redoc/` — جاهزة عبر drf-spectacular (لا تحتوي مخططات فعلية بعد).
- `GET /api/v1/_tenant/context` و`GET /api/v1/dashboard/stores/<uuid>/_debug` — **مؤقّتة/تشخيصية فقط**، غرضها إثبات أن `TenantMiddleware` يعمل عبر HTTP حقيقي (Host header ومسار الـ dashboard)، وستُحذف عند وصول نقاط النهاية الحقيقية.

---

## 5. Tests & Test Results (تشغيل فعلي، ليس افتراضًا)

```
40 passed in ~4s   (pytest, مقابل PostgreSQL 18.6 حقيقي عبر WSL2)
Coverage: 84% على apps/ (exceptions.py/logging.py أقل تغطية لأنها لم تُستخدم بعد من endpoint حقيقي — متوقّع لهذه المرحلة)
```

أهم ما تُثبته حزمة `tests/test_tenant_isolation.py` (بارامترية تلقائية على كل subclass من `TenantOwnedModel` — أي نموذج جديد يُضاف لاحقًا يدخل هذا الاختبار تلقائيًا أو يفشل CI إن لم يُسجَّل):
- Store A لا يستطيع **قراءة** صف Store B عبر `.unscoped` (يثبت RLS نفسها، لا مجرد فلترة Python).
- Store A لا يستطيع **تعديله** (`UPDATE` يُطابق صفرًا من الصفوف).
- Store A لا يستطيع **حذفه** (`DELETE` يُطابق صفرًا من الصفوف).
- محاولة **إدراج** صف يحمل `store_id` لمتجر آخر أثناء أن السياق الحالي متجر مختلف → **يُرفض من PostgreSQL نفسه** (RLS `WITH CHECK`) — هذا يحاكي مباشرة سيناريو "تغيير store_id في الـ body/URL".
- الطبقة السهلة (`Model.objects`) تُخفي بيانات المتجر الآخر أيضًا (طبقة أمان ثانية، ليست بديلًا عن RLS).
- اختبارات مستقلة لـ `Store` نفسه (الجذر التنانتي) — SELECT مفتوحة، UPDATE/DELETE مقيّدة بالسياق.
- اختبارات Celery: الإرسال بدون `store_id` يُرفض عند الإرسال؛ مهمّتان متتاليتان لمتجرين مختلفين لا تتسرّب أي منهما للأخرى؛ مهمة لمتجر A لا ترى بيانات متجر B فعليًا (`.count()` مُتحقَّق).
- اختبارات HTTP كاملة (Django test client حقيقي): تسلسل 5 طلبات لمضيفين مختلفين على نفس العميل يثبت عدم تسرّب السياق بينها إطلاقًا — وقد اكتشفتُ وأصلحتُ خللًا حقيقيًا هنا أثناء البناء (انظر أدناه).
- اختبارات صريحة على امتيازات الدور: `app_user` ليس superuser، ليس bypassrls، لا يملك الجداول.

### علّة حقيقية اكتُشفت وأُصلحت أثناء هذه المرحلة (تقرير صادق، لا إخفاء)
اختبار "لا تسرّب بين الطلبات" فشل أول مرة: `LocMemCache` المستخدم في `test.py` هو عملية مشتركة على مستوى العملية، ولا يُعاد ضبطه بين الاختبارات كما تُعاد قاعدة البيانات (transaction rollback). اختباران مختلفان استخدما نفس اسم المضيف، فاحتفظ الكاش بقيمة قديمة (متجر محذوف من اختبار سابق) وأعاد `None` خطأً. الإصلاح: `autouse fixture` في `backend/conftest.py` يمسح الكاش قبل/بعد كل اختبار. هذا درس تشغيلي حقيقي موثَّق في الكود نفسه.

---

## 6. Security Checks

| الفحص | النتيجة |
|---|---|
| `app_user` ليس superuser/bypassrls/createdb/createrole | ✅ مُتحقَّق من `pg_roles` مباشرة |
| `app_user` لا يملك أي جدول تنانتي | ✅ مُتحقَّق من `pg_tables.tableowner` |
| RLS مفعّلة فعليًا على الجداول التنانتية | ✅ مُتحقَّق من `pg_class.relrowsecurity` |
| `set_config` بمعامل مربوط (لا تنسيق نصي) | ✅ مراجعة كود |
| لا أسرار في Git | ✅ `.env` في `.gitignore`، `.env.example` بلا قيم حقيقية |
| Argon2 لكلمات المرور | ✅ `PASSWORD_HASHERS` |
| تسجيل مُنقَّى للأسرار | ✅ `SecretRedactionFilter` (يُخفي JWT/Bearer/كلمات مرور تلقائيًا) |
| `bandit` | ✅ صفر مشاكل (استثناءان موثَّقان بـ `nosec` لعبارات ليست أسرارًا فعليًا: اسم claim، مفتاح اختبار) |
| ruff / black / mypy / import-linter | ✅ كل الأربعة خضراء فعليًا (شُغِّلت، لا افتراضًا) |

---

## 7. Known Issues / قيود معروفة صراحة

1. **`docker-compose.yml` لم يُختبَر فعليًا** (لا Docker على جهاز التطوير) — مكتوب بعناية لكن غير مُتحقَّق تشغيليًا. يُرجى تجربته والإبلاغ.
2. نقاط `/api/v1/_tenant/context` و`/_debug` **مؤقّتة** ويجب حذفها عند وصول نقاط النهاية الحقيقية في Phase 2/3.
3. لا اختبارات E2E/Playwright بعد (لا يوجد frontend بعد — Phase 12+).
4. تغطية `exceptions.py`/`logging.py` جزئية لأنها غير مُستخدَمة من أي endpoint حقيقي بعد؛ ستكتمل تلقائيًا مع Phase 2.
5. Celery beat/worker غير مُختبرَين تحت broker حقيقي (استُخدم `CELERY_TASK_ALWAYS_EAGER=True` للاختبارات) — التحقّق تحت broker Redis حقيقي متعدد العمليات يبقى لـ Phase 19 (Production Setup) أو عند تشغيل docker-compose فعليًا.
6. منافذ WSL المحلية (15432/16379) خاصة بهذا الجهاز فقط بسبب تعارض مع Postgres أخرى مثبَّتة مسبقًا؛ لا علاقة لها بالإنتاج أو بـ docker-compose (الذي يستخدم شبكة Docker الداخلية).

---

## 8. المرحلة التالية (Phase 2 — Accounts & Auth)

- Registration / Login / Logout / Password reset / Email verification.
- JWT بعالَمين (`platform`/`storefront`) عبر BFF كما في التصميم.
- `StoreMembership` + `Role` + كتالوج صلاحيات RBAC.
- مصفوفة اختبارات صلاحيات كاملة (دور × endpoint).
- حذف نقاط `_debug` المؤقّتة عند توفّر بديل حقيقي.

لن أبدأ Phase 2 قبل موافقتك الصريحة.
