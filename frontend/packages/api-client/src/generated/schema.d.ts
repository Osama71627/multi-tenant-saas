export interface paths {
    "/api/v1/auth/email/verify/confirm": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post: operations["api_v1_auth_email_verify_confirm_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/email/verify/resend": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post: operations["api_v1_auth_email_verify_resend_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * @description Wraps SimpleJWT's TokenObtainPairView with the brute-force lockout
         *     from apps.accounts.lockout -- locked on (email, IP), see that
         *     module's docstring for why.
         *
         *     Phase 17: a platform-staff account (`is_platform_staff=True`) never
         *     gets a JWT from this endpoint directly -- see `_platform_staff_login`
         *     below and `apps.accounts.mfa_services`' module docstring for the full
         *     two-step design. Ordinary accounts are completely unaffected and keep
         *     the exact single-step flow this view always had.
         */
        post: operations["api_v1_auth_login_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post: operations["api_v1_auth_logout_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["api_v1_auth_me_retrieve"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/mfa/enroll/confirm": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * @description Second step of enrollment: {challenge_token, code} -> confirms the
         *     pending device, issues one-time recovery codes (returned RAW here,
         *     exactly once), and completes login with a full JWT (mfa=True).
         */
        post: operations["api_v1_auth_mfa_enroll_confirm_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/mfa/enroll/start": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * @description First step of enrollment (only reachable with a valid challenge from
         *     a login that returned `state: mfa_setup_required`): generates a
         *     pending TOTP secret and returns it for manual entry into an
         *     authenticator app, plus the equivalent `otpauth://` URI.
         */
        post: operations["api_v1_auth_mfa_enroll_start_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/mfa/verify": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * @description Second step of platform-staff login for an already-enrolled device:
         *     {challenge_token, code} -> full JWT (mfa=True). `code` may be a 6-digit
         *     TOTP code or a recovery code (see `_looks_like_recovery_code`).
         */
        post: operations["api_v1_auth_mfa_verify_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/password/reset": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post: operations["api_v1_auth_password_reset_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/password/reset/confirm": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post: operations["api_v1_auth_password_reset_confirm_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/refresh": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * @description Takes a refresh type JSON web token and returns an access type JSON web
         *     token if the refresh token is valid.
         */
        post: operations["api_v1_auth_refresh_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/register": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post: operations["api_v1_auth_register_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dashboard/stores": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * @description `GET /api/v1/dashboard/stores` -- the store switcher's data source
         *     (docs/ARCHITECTURE.md section 7.3): stores the current user has an
         *     ACTIVE membership in; see apps.stores.services.list_stores_for_user
         *     for why this is a legitimate cross-tenant read. `POST` is the
         *     existing store-provisioning endpoint, unchanged.
         */
        get: operations["api_v1_dashboard_stores_list"];
        put?: never;
        /**
         * @description `GET /api/v1/dashboard/stores` -- the store switcher's data source
         *     (docs/ARCHITECTURE.md section 7.3): stores the current user has an
         *     ACTIVE membership in; see apps.stores.services.list_stores_for_user
         *     for why this is a legitimate cross-tenant read. `POST` is the
         *     existing store-provisioning endpoint, unchanged.
         */
        post: operations["api_v1_dashboard_stores_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dashboard/stores/{store_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description 404 vs 403 semantics, and why: apps/stores/mixins.py:StoreScopedAPIView. */
        get: operations["api_v1_dashboard_stores_retrieve"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** @description 404 vs 403 semantics, and why: apps/stores/mixins.py:StoreScopedAPIView. */
        patch: operations["api_v1_dashboard_stores_partial_update"];
        trace?: never;
    };
    "/api/v1/dashboard/stores/{store_id}/analytics/overview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * @description Base class for any `/api/v1/dashboard/stores/<uuid:store_id>/...`
         *     endpoint. Relies on `TenantMiddleware` having already resolved the
         *     path's `store_id` into `request.tenant_store` (path-based, Host
         *     header ignored -- apps/stores/middleware.py).
         *
         *     404 vs 403 distinguished on purpose (same reasoning as Phase 3's
         *     StoreDetailView, docs/PHASE_3_REPORT.md): a store's existence isn't
         *     secret (its RLS SELECT policy is intentionally open), but catalog
         *     resources INSIDE it are fully RLS-restricted with no such exception
         *     -- so once past this gate, an ordinary tenant-scoped query for a
         *     resource that doesn't exist in this store naturally 404s via
         *     `DoesNotExist`, with no separate leak to worry about.
         *
         *     Sets `self.store` for subclasses to use.
         */
        get: operations["api_v1_dashboard_stores_analytics_overview_retrieve"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dashboard/stores/{store_id}/categories": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * @description Base class for any `/api/v1/dashboard/stores/<uuid:store_id>/...`
         *     endpoint. Relies on `TenantMiddleware` having already resolved the
         *     path's `store_id` into `request.tenant_store` (path-based, Host
         *     header ignored -- apps/stores/middleware.py).
         *
         *     404 vs 403 distinguished on purpose (same reasoning as Phase 3's
         *     StoreDetailView, docs/PHASE_3_REPORT.md): a store's existence isn't
         *     secret (its RLS SELECT policy is intentionally open), but catalog
         *     resources INSIDE it are fully RLS-restricted with no such exception
         *     -- so once past this gate, an ordinary tenant-scoped query for a
         *     resource that doesn't exist in this store naturally 404s via
         *     `DoesNotExist`, with no separate leak to worry about.
         *
         *     Sets `self.store` for subclasses to use.
         */
        get: operations["api_v1_dashboard_stores_categories_retrieve"];
        put?: never;
        /**
         * @description Base class for any `/api/v1/dashboard/stores/<uuid:store_id>/...`
         *     endpoint. Relies on `TenantMiddleware` having already resolved the
         *     path's `store_id` into `request.tenant_store` (path-based, Host
         *     header ignored -- apps/stores/middleware.py).
         *
         *     404 vs 403 distinguished on purpose (same reasoning as Phase 3's
         *     StoreDetailView, docs/PHASE_3_REPORT.md): a store's existence isn't
         *     secret (its RLS SELECT policy is intentionally open), but catalog
         *     resources INSIDE it are fully RLS-restricted with no such exception
         *     -- so once past this gate, an ordinary tenant-scoped query for a
         *     resource that doesn't exist in this store naturally 404s via
         *     `DoesNotExist`, with no separate leak to worry about.
         *
         *     Sets `self.store` for subclasses to use.
         */
        post: operations["api_v1_dashboard_stores_categories_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dashboard/stores/{store_id}/inventory/adjust": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * @description Base class for any `/api/v1/dashboard/stores/<uuid:store_id>/...`
         *     endpoint. Relies on `TenantMiddleware` having already resolved the
         *     path's `store_id` into `request.tenant_store` (path-based, Host
         *     header ignored -- apps/stores/middleware.py).
         *
         *     404 vs 403 distinguished on purpose (same reasoning as Phase 3's
         *     StoreDetailView, docs/PHASE_3_REPORT.md): a store's existence isn't
         *     secret (its RLS SELECT policy is intentionally open), but catalog
         *     resources INSIDE it are fully RLS-restricted with no such exception
         *     -- so once past this gate, an ordinary tenant-scoped query for a
         *     resource that doesn't exist in this store naturally 404s via
         *     `DoesNotExist`, with no separate leak to worry about.
         *
         *     Sets `self.store` for subclasses to use.
         */
        post: operations["api_v1_dashboard_stores_inventory_adjust_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dashboard/stores/{store_id}/inventory/balances": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * @description Base class for any `/api/v1/dashboard/stores/<uuid:store_id>/...`
         *     endpoint. Relies on `TenantMiddleware` having already resolved the
         *     path's `store_id` into `request.tenant_store` (path-based, Host
         *     header ignored -- apps/stores/middleware.py).
         *
         *     404 vs 403 distinguished on purpose (same reasoning as Phase 3's
         *     StoreDetailView, docs/PHASE_3_REPORT.md): a store's existence isn't
         *     secret (its RLS SELECT policy is intentionally open), but catalog
         *     resources INSIDE it are fully RLS-restricted with no such exception
         *     -- so once past this gate, an ordinary tenant-scoped query for a
         *     resource that doesn't exist in this store naturally 404s via
         *     `DoesNotExist`, with no separate leak to worry about.
         *
         *     Sets `self.store` for subclasses to use.
         */
        get: operations["api_v1_dashboard_stores_inventory_balances_list"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dashboard/stores/{store_id}/inventory/locations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * @description Base class for any `/api/v1/dashboard/stores/<uuid:store_id>/...`
         *     endpoint. Relies on `TenantMiddleware` having already resolved the
         *     path's `store_id` into `request.tenant_store` (path-based, Host
         *     header ignored -- apps/stores/middleware.py).
         *
         *     404 vs 403 distinguished on purpose (same reasoning as Phase 3's
         *     StoreDetailView, docs/PHASE_3_REPORT.md): a store's existence isn't
         *     secret (its RLS SELECT policy is intentionally open), but catalog
         *     resources INSIDE it are fully RLS-restricted with no such exception
         *     -- so once past this gate, an ordinary tenant-scoped query for a
         *     resource that doesn't exist in this store naturally 404s via
         *     `DoesNotExist`, with no separate leak to worry about.
         *
         *     Sets `self.store` for subclasses to use.
         */
        get: operations["api_v1_dashboard_stores_inventory_locations_list"];
        put?: never;
        /**
         * @description Base class for any `/api/v1/dashboard/stores/<uuid:store_id>/...`
         *     endpoint. Relies on `TenantMiddleware` having already resolved the
         *     path's `store_id` into `request.tenant_store` (path-based, Host
         *     header ignored -- apps/stores/middleware.py).
         *
         *     404 vs 403 distinguished on purpose (same reasoning as Phase 3's
         *     StoreDetailView, docs/PHASE_3_REPORT.md): a store's existence isn't
         *     secret (its RLS SELECT policy is intentionally open), but catalog
         *     resources INSIDE it are fully RLS-restricted with no such exception
         *     -- so once past this gate, an ordinary tenant-scoped query for a
         *     resource that doesn't exist in this store naturally 404s via
         *     `DoesNotExist`, with no separate leak to worry about.
         *
         *     Sets `self.store` for subclasses to use.
         */
        post: operations["api_v1_dashboard_stores_inventory_locations_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dashboard/stores/{store_id}/inventory/movements": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * @description Base class for any `/api/v1/dashboard/stores/<uuid:store_id>/...`
         *     endpoint. Relies on `TenantMiddleware` having already resolved the
         *     path's `store_id` into `request.tenant_store` (path-based, Host
         *     header ignored -- apps/stores/middleware.py).
         *
         *     404 vs 403 distinguished on purpose (same reasoning as Phase 3's
         *     StoreDetailView, docs/PHASE_3_REPORT.md): a store's existence isn't
         *     secret (its RLS SELECT policy is intentionally open), but catalog
         *     resources INSIDE it are fully RLS-restricted with no such exception
         *     -- so once past this gate, an ordinary tenant-scoped query for a
         *     resource that doesn't exist in this store naturally 404s via
         *     `DoesNotExist`, with no separate leak to worry about.
         *
         *     Sets `self.store` for subclasses to use.
         */
        get: operations["api_v1_dashboard_stores_inventory_movements_retrieve"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dashboard/stores/{store_id}/orders": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * @description Base class for any `/api/v1/dashboard/stores/<uuid:store_id>/...`
         *     endpoint. Relies on `TenantMiddleware` having already resolved the
         *     path's `store_id` into `request.tenant_store` (path-based, Host
         *     header ignored -- apps/stores/middleware.py).
         *
         *     404 vs 403 distinguished on purpose (same reasoning as Phase 3's
         *     StoreDetailView, docs/PHASE_3_REPORT.md): a store's existence isn't
         *     secret (its RLS SELECT policy is intentionally open), but catalog
         *     resources INSIDE it are fully RLS-restricted with no such exception
         *     -- so once past this gate, an ordinary tenant-scoped query for a
         *     resource that doesn't exist in this store naturally 404s via
         *     `DoesNotExist`, with no separate leak to worry about.
         *
         *     Sets `self.store` for subclasses to use.
         */
        get: operations["api_v1_dashboard_stores_orders_list"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dashboard/stores/{store_id}/orders/{order_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * @description Base class for any `/api/v1/dashboard/stores/<uuid:store_id>/...`
         *     endpoint. Relies on `TenantMiddleware` having already resolved the
         *     path's `store_id` into `request.tenant_store` (path-based, Host
         *     header ignored -- apps/stores/middleware.py).
         *
         *     404 vs 403 distinguished on purpose (same reasoning as Phase 3's
         *     StoreDetailView, docs/PHASE_3_REPORT.md): a store's existence isn't
         *     secret (its RLS SELECT policy is intentionally open), but catalog
         *     resources INSIDE it are fully RLS-restricted with no such exception
         *     -- so once past this gate, an ordinary tenant-scoped query for a
         *     resource that doesn't exist in this store naturally 404s via
         *     `DoesNotExist`, with no separate leak to worry about.
         *
         *     Sets `self.store` for subclasses to use.
         */
        get: operations["api_v1_dashboard_stores_orders_retrieve"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dashboard/stores/{store_id}/payment-intents/{payment_intent_id}/capture-cod": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * @description Base class for any `/api/v1/dashboard/stores/<uuid:store_id>/...`
         *     endpoint. Relies on `TenantMiddleware` having already resolved the
         *     path's `store_id` into `request.tenant_store` (path-based, Host
         *     header ignored -- apps/stores/middleware.py).
         *
         *     404 vs 403 distinguished on purpose (same reasoning as Phase 3's
         *     StoreDetailView, docs/PHASE_3_REPORT.md): a store's existence isn't
         *     secret (its RLS SELECT policy is intentionally open), but catalog
         *     resources INSIDE it are fully RLS-restricted with no such exception
         *     -- so once past this gate, an ordinary tenant-scoped query for a
         *     resource that doesn't exist in this store naturally 404s via
         *     `DoesNotExist`, with no separate leak to worry about.
         *
         *     Sets `self.store` for subclasses to use.
         */
        post: operations["api_v1_dashboard_stores_payment_intents_capture_cod_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dashboard/stores/{store_id}/payments/providers": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * @description Base class for any `/api/v1/dashboard/stores/<uuid:store_id>/...`
         *     endpoint. Relies on `TenantMiddleware` having already resolved the
         *     path's `store_id` into `request.tenant_store` (path-based, Host
         *     header ignored -- apps/stores/middleware.py).
         *
         *     404 vs 403 distinguished on purpose (same reasoning as Phase 3's
         *     StoreDetailView, docs/PHASE_3_REPORT.md): a store's existence isn't
         *     secret (its RLS SELECT policy is intentionally open), but catalog
         *     resources INSIDE it are fully RLS-restricted with no such exception
         *     -- so once past this gate, an ordinary tenant-scoped query for a
         *     resource that doesn't exist in this store naturally 404s via
         *     `DoesNotExist`, with no separate leak to worry about.
         *
         *     Sets `self.store` for subclasses to use.
         */
        get: operations["api_v1_dashboard_stores_payments_providers_list"];
        put?: never;
        /**
         * @description Base class for any `/api/v1/dashboard/stores/<uuid:store_id>/...`
         *     endpoint. Relies on `TenantMiddleware` having already resolved the
         *     path's `store_id` into `request.tenant_store` (path-based, Host
         *     header ignored -- apps/stores/middleware.py).
         *
         *     404 vs 403 distinguished on purpose (same reasoning as Phase 3's
         *     StoreDetailView, docs/PHASE_3_REPORT.md): a store's existence isn't
         *     secret (its RLS SELECT policy is intentionally open), but catalog
         *     resources INSIDE it are fully RLS-restricted with no such exception
         *     -- so once past this gate, an ordinary tenant-scoped query for a
         *     resource that doesn't exist in this store naturally 404s via
         *     `DoesNotExist`, with no separate leak to worry about.
         *
         *     Sets `self.store` for subclasses to use.
         */
        post: operations["api_v1_dashboard_stores_payments_providers_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dashboard/stores/{store_id}/pricing/coupons": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * @description Base class for any `/api/v1/dashboard/stores/<uuid:store_id>/...`
         *     endpoint. Relies on `TenantMiddleware` having already resolved the
         *     path's `store_id` into `request.tenant_store` (path-based, Host
         *     header ignored -- apps/stores/middleware.py).
         *
         *     404 vs 403 distinguished on purpose (same reasoning as Phase 3's
         *     StoreDetailView, docs/PHASE_3_REPORT.md): a store's existence isn't
         *     secret (its RLS SELECT policy is intentionally open), but catalog
         *     resources INSIDE it are fully RLS-restricted with no such exception
         *     -- so once past this gate, an ordinary tenant-scoped query for a
         *     resource that doesn't exist in this store naturally 404s via
         *     `DoesNotExist`, with no separate leak to worry about.
         *
         *     Sets `self.store` for subclasses to use.
         */
        get: operations["api_v1_dashboard_stores_pricing_coupons_retrieve"];
        put?: never;
        /**
         * @description Base class for any `/api/v1/dashboard/stores/<uuid:store_id>/...`
         *     endpoint. Relies on `TenantMiddleware` having already resolved the
         *     path's `store_id` into `request.tenant_store` (path-based, Host
         *     header ignored -- apps/stores/middleware.py).
         *
         *     404 vs 403 distinguished on purpose (same reasoning as Phase 3's
         *     StoreDetailView, docs/PHASE_3_REPORT.md): a store's existence isn't
         *     secret (its RLS SELECT policy is intentionally open), but catalog
         *     resources INSIDE it are fully RLS-restricted with no such exception
         *     -- so once past this gate, an ordinary tenant-scoped query for a
         *     resource that doesn't exist in this store naturally 404s via
         *     `DoesNotExist`, with no separate leak to worry about.
         *
         *     Sets `self.store` for subclasses to use.
         */
        post: operations["api_v1_dashboard_stores_pricing_coupons_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dashboard/stores/{store_id}/pricing/tax-rates": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * @description Base class for any `/api/v1/dashboard/stores/<uuid:store_id>/...`
         *     endpoint. Relies on `TenantMiddleware` having already resolved the
         *     path's `store_id` into `request.tenant_store` (path-based, Host
         *     header ignored -- apps/stores/middleware.py).
         *
         *     404 vs 403 distinguished on purpose (same reasoning as Phase 3's
         *     StoreDetailView, docs/PHASE_3_REPORT.md): a store's existence isn't
         *     secret (its RLS SELECT policy is intentionally open), but catalog
         *     resources INSIDE it are fully RLS-restricted with no such exception
         *     -- so once past this gate, an ordinary tenant-scoped query for a
         *     resource that doesn't exist in this store naturally 404s via
         *     `DoesNotExist`, with no separate leak to worry about.
         *
         *     Sets `self.store` for subclasses to use.
         */
        get: operations["api_v1_dashboard_stores_pricing_tax_rates_retrieve"];
        put?: never;
        /**
         * @description Base class for any `/api/v1/dashboard/stores/<uuid:store_id>/...`
         *     endpoint. Relies on `TenantMiddleware` having already resolved the
         *     path's `store_id` into `request.tenant_store` (path-based, Host
         *     header ignored -- apps/stores/middleware.py).
         *
         *     404 vs 403 distinguished on purpose (same reasoning as Phase 3's
         *     StoreDetailView, docs/PHASE_3_REPORT.md): a store's existence isn't
         *     secret (its RLS SELECT policy is intentionally open), but catalog
         *     resources INSIDE it are fully RLS-restricted with no such exception
         *     -- so once past this gate, an ordinary tenant-scoped query for a
         *     resource that doesn't exist in this store naturally 404s via
         *     `DoesNotExist`, with no separate leak to worry about.
         *
         *     Sets `self.store` for subclasses to use.
         */
        post: operations["api_v1_dashboard_stores_pricing_tax_rates_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dashboard/stores/{store_id}/products": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * @description Base class for any `/api/v1/dashboard/stores/<uuid:store_id>/...`
         *     endpoint. Relies on `TenantMiddleware` having already resolved the
         *     path's `store_id` into `request.tenant_store` (path-based, Host
         *     header ignored -- apps/stores/middleware.py).
         *
         *     404 vs 403 distinguished on purpose (same reasoning as Phase 3's
         *     StoreDetailView, docs/PHASE_3_REPORT.md): a store's existence isn't
         *     secret (its RLS SELECT policy is intentionally open), but catalog
         *     resources INSIDE it are fully RLS-restricted with no such exception
         *     -- so once past this gate, an ordinary tenant-scoped query for a
         *     resource that doesn't exist in this store naturally 404s via
         *     `DoesNotExist`, with no separate leak to worry about.
         *
         *     Sets `self.store` for subclasses to use.
         */
        get: operations["api_v1_dashboard_stores_products_list"];
        put?: never;
        /**
         * @description Base class for any `/api/v1/dashboard/stores/<uuid:store_id>/...`
         *     endpoint. Relies on `TenantMiddleware` having already resolved the
         *     path's `store_id` into `request.tenant_store` (path-based, Host
         *     header ignored -- apps/stores/middleware.py).
         *
         *     404 vs 403 distinguished on purpose (same reasoning as Phase 3's
         *     StoreDetailView, docs/PHASE_3_REPORT.md): a store's existence isn't
         *     secret (its RLS SELECT policy is intentionally open), but catalog
         *     resources INSIDE it are fully RLS-restricted with no such exception
         *     -- so once past this gate, an ordinary tenant-scoped query for a
         *     resource that doesn't exist in this store naturally 404s via
         *     `DoesNotExist`, with no separate leak to worry about.
         *
         *     Sets `self.store` for subclasses to use.
         */
        post: operations["api_v1_dashboard_stores_products_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dashboard/stores/{store_id}/products/{product_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * @description Base class for any `/api/v1/dashboard/stores/<uuid:store_id>/...`
         *     endpoint. Relies on `TenantMiddleware` having already resolved the
         *     path's `store_id` into `request.tenant_store` (path-based, Host
         *     header ignored -- apps/stores/middleware.py).
         *
         *     404 vs 403 distinguished on purpose (same reasoning as Phase 3's
         *     StoreDetailView, docs/PHASE_3_REPORT.md): a store's existence isn't
         *     secret (its RLS SELECT policy is intentionally open), but catalog
         *     resources INSIDE it are fully RLS-restricted with no such exception
         *     -- so once past this gate, an ordinary tenant-scoped query for a
         *     resource that doesn't exist in this store naturally 404s via
         *     `DoesNotExist`, with no separate leak to worry about.
         *
         *     Sets `self.store` for subclasses to use.
         */
        get: operations["api_v1_dashboard_stores_products_retrieve"];
        put?: never;
        post?: never;
        /**
         * @description Base class for any `/api/v1/dashboard/stores/<uuid:store_id>/...`
         *     endpoint. Relies on `TenantMiddleware` having already resolved the
         *     path's `store_id` into `request.tenant_store` (path-based, Host
         *     header ignored -- apps/stores/middleware.py).
         *
         *     404 vs 403 distinguished on purpose (same reasoning as Phase 3's
         *     StoreDetailView, docs/PHASE_3_REPORT.md): a store's existence isn't
         *     secret (its RLS SELECT policy is intentionally open), but catalog
         *     resources INSIDE it are fully RLS-restricted with no such exception
         *     -- so once past this gate, an ordinary tenant-scoped query for a
         *     resource that doesn't exist in this store naturally 404s via
         *     `DoesNotExist`, with no separate leak to worry about.
         *
         *     Sets `self.store` for subclasses to use.
         */
        delete: operations["api_v1_dashboard_stores_products_destroy"];
        options?: never;
        head?: never;
        /**
         * @description Base class for any `/api/v1/dashboard/stores/<uuid:store_id>/...`
         *     endpoint. Relies on `TenantMiddleware` having already resolved the
         *     path's `store_id` into `request.tenant_store` (path-based, Host
         *     header ignored -- apps/stores/middleware.py).
         *
         *     404 vs 403 distinguished on purpose (same reasoning as Phase 3's
         *     StoreDetailView, docs/PHASE_3_REPORT.md): a store's existence isn't
         *     secret (its RLS SELECT policy is intentionally open), but catalog
         *     resources INSIDE it are fully RLS-restricted with no such exception
         *     -- so once past this gate, an ordinary tenant-scoped query for a
         *     resource that doesn't exist in this store naturally 404s via
         *     `DoesNotExist`, with no separate leak to worry about.
         *
         *     Sets `self.store` for subclasses to use.
         */
        patch: operations["api_v1_dashboard_stores_products_partial_update"];
        trace?: never;
    };
    "/api/v1/dashboard/stores/{store_id}/products/{product_id}/options": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * @description Base class for any `/api/v1/dashboard/stores/<uuid:store_id>/...`
         *     endpoint. Relies on `TenantMiddleware` having already resolved the
         *     path's `store_id` into `request.tenant_store` (path-based, Host
         *     header ignored -- apps/stores/middleware.py).
         *
         *     404 vs 403 distinguished on purpose (same reasoning as Phase 3's
         *     StoreDetailView, docs/PHASE_3_REPORT.md): a store's existence isn't
         *     secret (its RLS SELECT policy is intentionally open), but catalog
         *     resources INSIDE it are fully RLS-restricted with no such exception
         *     -- so once past this gate, an ordinary tenant-scoped query for a
         *     resource that doesn't exist in this store naturally 404s via
         *     `DoesNotExist`, with no separate leak to worry about.
         *
         *     Sets `self.store` for subclasses to use.
         */
        post: operations["api_v1_dashboard_stores_products_options_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dashboard/stores/{store_id}/products/{product_id}/options/{option_id}/values": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * @description Base class for any `/api/v1/dashboard/stores/<uuid:store_id>/...`
         *     endpoint. Relies on `TenantMiddleware` having already resolved the
         *     path's `store_id` into `request.tenant_store` (path-based, Host
         *     header ignored -- apps/stores/middleware.py).
         *
         *     404 vs 403 distinguished on purpose (same reasoning as Phase 3's
         *     StoreDetailView, docs/PHASE_3_REPORT.md): a store's existence isn't
         *     secret (its RLS SELECT policy is intentionally open), but catalog
         *     resources INSIDE it are fully RLS-restricted with no such exception
         *     -- so once past this gate, an ordinary tenant-scoped query for a
         *     resource that doesn't exist in this store naturally 404s via
         *     `DoesNotExist`, with no separate leak to worry about.
         *
         *     Sets `self.store` for subclasses to use.
         */
        post: operations["api_v1_dashboard_stores_products_options_values_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dashboard/stores/{store_id}/products/{product_id}/variants": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * @description Base class for any `/api/v1/dashboard/stores/<uuid:store_id>/...`
         *     endpoint. Relies on `TenantMiddleware` having already resolved the
         *     path's `store_id` into `request.tenant_store` (path-based, Host
         *     header ignored -- apps/stores/middleware.py).
         *
         *     404 vs 403 distinguished on purpose (same reasoning as Phase 3's
         *     StoreDetailView, docs/PHASE_3_REPORT.md): a store's existence isn't
         *     secret (its RLS SELECT policy is intentionally open), but catalog
         *     resources INSIDE it are fully RLS-restricted with no such exception
         *     -- so once past this gate, an ordinary tenant-scoped query for a
         *     resource that doesn't exist in this store naturally 404s via
         *     `DoesNotExist`, with no separate leak to worry about.
         *
         *     Sets `self.store` for subclasses to use.
         */
        post: operations["api_v1_dashboard_stores_products_variants_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dashboard/stores/{store_id}/products/{product_id}/variants/{variant_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /**
         * @description Base class for any `/api/v1/dashboard/stores/<uuid:store_id>/...`
         *     endpoint. Relies on `TenantMiddleware` having already resolved the
         *     path's `store_id` into `request.tenant_store` (path-based, Host
         *     header ignored -- apps/stores/middleware.py).
         *
         *     404 vs 403 distinguished on purpose (same reasoning as Phase 3's
         *     StoreDetailView, docs/PHASE_3_REPORT.md): a store's existence isn't
         *     secret (its RLS SELECT policy is intentionally open), but catalog
         *     resources INSIDE it are fully RLS-restricted with no such exception
         *     -- so once past this gate, an ordinary tenant-scoped query for a
         *     resource that doesn't exist in this store naturally 404s via
         *     `DoesNotExist`, with no separate leak to worry about.
         *
         *     Sets `self.store` for subclasses to use.
         */
        delete: operations["api_v1_dashboard_stores_products_variants_destroy"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dashboard/stores/{store_id}/shipping/methods/{method_id}/rates": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * @description Base class for any `/api/v1/dashboard/stores/<uuid:store_id>/...`
         *     endpoint. Relies on `TenantMiddleware` having already resolved the
         *     path's `store_id` into `request.tenant_store` (path-based, Host
         *     header ignored -- apps/stores/middleware.py).
         *
         *     404 vs 403 distinguished on purpose (same reasoning as Phase 3's
         *     StoreDetailView, docs/PHASE_3_REPORT.md): a store's existence isn't
         *     secret (its RLS SELECT policy is intentionally open), but catalog
         *     resources INSIDE it are fully RLS-restricted with no such exception
         *     -- so once past this gate, an ordinary tenant-scoped query for a
         *     resource that doesn't exist in this store naturally 404s via
         *     `DoesNotExist`, with no separate leak to worry about.
         *
         *     Sets `self.store` for subclasses to use.
         */
        get: operations["api_v1_dashboard_stores_shipping_methods_rates_list"];
        put?: never;
        /**
         * @description Base class for any `/api/v1/dashboard/stores/<uuid:store_id>/...`
         *     endpoint. Relies on `TenantMiddleware` having already resolved the
         *     path's `store_id` into `request.tenant_store` (path-based, Host
         *     header ignored -- apps/stores/middleware.py).
         *
         *     404 vs 403 distinguished on purpose (same reasoning as Phase 3's
         *     StoreDetailView, docs/PHASE_3_REPORT.md): a store's existence isn't
         *     secret (its RLS SELECT policy is intentionally open), but catalog
         *     resources INSIDE it are fully RLS-restricted with no such exception
         *     -- so once past this gate, an ordinary tenant-scoped query for a
         *     resource that doesn't exist in this store naturally 404s via
         *     `DoesNotExist`, with no separate leak to worry about.
         *
         *     Sets `self.store` for subclasses to use.
         */
        post: operations["api_v1_dashboard_stores_shipping_methods_rates_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dashboard/stores/{store_id}/shipping/zones": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * @description Base class for any `/api/v1/dashboard/stores/<uuid:store_id>/...`
         *     endpoint. Relies on `TenantMiddleware` having already resolved the
         *     path's `store_id` into `request.tenant_store` (path-based, Host
         *     header ignored -- apps/stores/middleware.py).
         *
         *     404 vs 403 distinguished on purpose (same reasoning as Phase 3's
         *     StoreDetailView, docs/PHASE_3_REPORT.md): a store's existence isn't
         *     secret (its RLS SELECT policy is intentionally open), but catalog
         *     resources INSIDE it are fully RLS-restricted with no such exception
         *     -- so once past this gate, an ordinary tenant-scoped query for a
         *     resource that doesn't exist in this store naturally 404s via
         *     `DoesNotExist`, with no separate leak to worry about.
         *
         *     Sets `self.store` for subclasses to use.
         */
        get: operations["api_v1_dashboard_stores_shipping_zones_list"];
        put?: never;
        /**
         * @description Base class for any `/api/v1/dashboard/stores/<uuid:store_id>/...`
         *     endpoint. Relies on `TenantMiddleware` having already resolved the
         *     path's `store_id` into `request.tenant_store` (path-based, Host
         *     header ignored -- apps/stores/middleware.py).
         *
         *     404 vs 403 distinguished on purpose (same reasoning as Phase 3's
         *     StoreDetailView, docs/PHASE_3_REPORT.md): a store's existence isn't
         *     secret (its RLS SELECT policy is intentionally open), but catalog
         *     resources INSIDE it are fully RLS-restricted with no such exception
         *     -- so once past this gate, an ordinary tenant-scoped query for a
         *     resource that doesn't exist in this store naturally 404s via
         *     `DoesNotExist`, with no separate leak to worry about.
         *
         *     Sets `self.store` for subclasses to use.
         */
        post: operations["api_v1_dashboard_stores_shipping_zones_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dashboard/stores/{store_id}/shipping/zones/{zone_id}/methods": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * @description Base class for any `/api/v1/dashboard/stores/<uuid:store_id>/...`
         *     endpoint. Relies on `TenantMiddleware` having already resolved the
         *     path's `store_id` into `request.tenant_store` (path-based, Host
         *     header ignored -- apps/stores/middleware.py).
         *
         *     404 vs 403 distinguished on purpose (same reasoning as Phase 3's
         *     StoreDetailView, docs/PHASE_3_REPORT.md): a store's existence isn't
         *     secret (its RLS SELECT policy is intentionally open), but catalog
         *     resources INSIDE it are fully RLS-restricted with no such exception
         *     -- so once past this gate, an ordinary tenant-scoped query for a
         *     resource that doesn't exist in this store naturally 404s via
         *     `DoesNotExist`, with no separate leak to worry about.
         *
         *     Sets `self.store` for subclasses to use.
         */
        get: operations["api_v1_dashboard_stores_shipping_zones_methods_list"];
        put?: never;
        /**
         * @description Base class for any `/api/v1/dashboard/stores/<uuid:store_id>/...`
         *     endpoint. Relies on `TenantMiddleware` having already resolved the
         *     path's `store_id` into `request.tenant_store` (path-based, Host
         *     header ignored -- apps/stores/middleware.py).
         *
         *     404 vs 403 distinguished on purpose (same reasoning as Phase 3's
         *     StoreDetailView, docs/PHASE_3_REPORT.md): a store's existence isn't
         *     secret (its RLS SELECT policy is intentionally open), but catalog
         *     resources INSIDE it are fully RLS-restricted with no such exception
         *     -- so once past this gate, an ordinary tenant-scoped query for a
         *     resource that doesn't exist in this store naturally 404s via
         *     `DoesNotExist`, with no separate leak to worry about.
         *
         *     Sets `self.store` for subclasses to use.
         */
        post: operations["api_v1_dashboard_stores_shipping_zones_methods_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dashboard/stores/{store_id}/subscription": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * @description Base class for any `/api/v1/dashboard/stores/<uuid:store_id>/...`
         *     endpoint. Relies on `TenantMiddleware` having already resolved the
         *     path's `store_id` into `request.tenant_store` (path-based, Host
         *     header ignored -- apps/stores/middleware.py).
         *
         *     404 vs 403 distinguished on purpose (same reasoning as Phase 3's
         *     StoreDetailView, docs/PHASE_3_REPORT.md): a store's existence isn't
         *     secret (its RLS SELECT policy is intentionally open), but catalog
         *     resources INSIDE it are fully RLS-restricted with no such exception
         *     -- so once past this gate, an ordinary tenant-scoped query for a
         *     resource that doesn't exist in this store naturally 404s via
         *     `DoesNotExist`, with no separate leak to worry about.
         *
         *     Sets `self.store` for subclasses to use.
         */
        get: operations["api_v1_dashboard_stores_subscription_retrieve"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dashboard/stores/{store_id}/supplier-products/{supplier_product_id}/promote": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * @description Base class for any `/api/v1/dashboard/stores/<uuid:store_id>/...`
         *     endpoint. Relies on `TenantMiddleware` having already resolved the
         *     path's `store_id` into `request.tenant_store` (path-based, Host
         *     header ignored -- apps/stores/middleware.py).
         *
         *     404 vs 403 distinguished on purpose (same reasoning as Phase 3's
         *     StoreDetailView, docs/PHASE_3_REPORT.md): a store's existence isn't
         *     secret (its RLS SELECT policy is intentionally open), but catalog
         *     resources INSIDE it are fully RLS-restricted with no such exception
         *     -- so once past this gate, an ordinary tenant-scoped query for a
         *     resource that doesn't exist in this store naturally 404s via
         *     `DoesNotExist`, with no separate leak to worry about.
         *
         *     Sets `self.store` for subclasses to use.
         */
        post: operations["api_v1_dashboard_stores_supplier_products_promote_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dashboard/stores/{store_id}/suppliers": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * @description Base class for any `/api/v1/dashboard/stores/<uuid:store_id>/...`
         *     endpoint. Relies on `TenantMiddleware` having already resolved the
         *     path's `store_id` into `request.tenant_store` (path-based, Host
         *     header ignored -- apps/stores/middleware.py).
         *
         *     404 vs 403 distinguished on purpose (same reasoning as Phase 3's
         *     StoreDetailView, docs/PHASE_3_REPORT.md): a store's existence isn't
         *     secret (its RLS SELECT policy is intentionally open), but catalog
         *     resources INSIDE it are fully RLS-restricted with no such exception
         *     -- so once past this gate, an ordinary tenant-scoped query for a
         *     resource that doesn't exist in this store naturally 404s via
         *     `DoesNotExist`, with no separate leak to worry about.
         *
         *     Sets `self.store` for subclasses to use.
         */
        get: operations["api_v1_dashboard_stores_suppliers_list"];
        put?: never;
        /**
         * @description Base class for any `/api/v1/dashboard/stores/<uuid:store_id>/...`
         *     endpoint. Relies on `TenantMiddleware` having already resolved the
         *     path's `store_id` into `request.tenant_store` (path-based, Host
         *     header ignored -- apps/stores/middleware.py).
         *
         *     404 vs 403 distinguished on purpose (same reasoning as Phase 3's
         *     StoreDetailView, docs/PHASE_3_REPORT.md): a store's existence isn't
         *     secret (its RLS SELECT policy is intentionally open), but catalog
         *     resources INSIDE it are fully RLS-restricted with no such exception
         *     -- so once past this gate, an ordinary tenant-scoped query for a
         *     resource that doesn't exist in this store naturally 404s via
         *     `DoesNotExist`, with no separate leak to worry about.
         *
         *     Sets `self.store` for subclasses to use.
         */
        post: operations["api_v1_dashboard_stores_suppliers_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dashboard/stores/{store_id}/suppliers/{supplier_id}/products": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * @description Base class for any `/api/v1/dashboard/stores/<uuid:store_id>/...`
         *     endpoint. Relies on `TenantMiddleware` having already resolved the
         *     path's `store_id` into `request.tenant_store` (path-based, Host
         *     header ignored -- apps/stores/middleware.py).
         *
         *     404 vs 403 distinguished on purpose (same reasoning as Phase 3's
         *     StoreDetailView, docs/PHASE_3_REPORT.md): a store's existence isn't
         *     secret (its RLS SELECT policy is intentionally open), but catalog
         *     resources INSIDE it are fully RLS-restricted with no such exception
         *     -- so once past this gate, an ordinary tenant-scoped query for a
         *     resource that doesn't exist in this store naturally 404s via
         *     `DoesNotExist`, with no separate leak to worry about.
         *
         *     Sets `self.store` for subclasses to use.
         */
        get: operations["api_v1_dashboard_stores_suppliers_products_list"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dashboard/stores/{store_id}/suppliers/{supplier_id}/sync": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * @description Base class for any `/api/v1/dashboard/stores/<uuid:store_id>/...`
         *     endpoint. Relies on `TenantMiddleware` having already resolved the
         *     path's `store_id` into `request.tenant_store` (path-based, Host
         *     header ignored -- apps/stores/middleware.py).
         *
         *     404 vs 403 distinguished on purpose (same reasoning as Phase 3's
         *     StoreDetailView, docs/PHASE_3_REPORT.md): a store's existence isn't
         *     secret (its RLS SELECT policy is intentionally open), but catalog
         *     resources INSIDE it are fully RLS-restricted with no such exception
         *     -- so once past this gate, an ordinary tenant-scoped query for a
         *     resource that doesn't exist in this store naturally 404s via
         *     `DoesNotExist`, with no separate leak to worry about.
         *
         *     Sets `self.store` for subclasses to use.
         */
        post: operations["api_v1_dashboard_stores_suppliers_sync_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dashboard/stores/{store_id}/tags": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * @description Base class for any `/api/v1/dashboard/stores/<uuid:store_id>/...`
         *     endpoint. Relies on `TenantMiddleware` having already resolved the
         *     path's `store_id` into `request.tenant_store` (path-based, Host
         *     header ignored -- apps/stores/middleware.py).
         *
         *     404 vs 403 distinguished on purpose (same reasoning as Phase 3's
         *     StoreDetailView, docs/PHASE_3_REPORT.md): a store's existence isn't
         *     secret (its RLS SELECT policy is intentionally open), but catalog
         *     resources INSIDE it are fully RLS-restricted with no such exception
         *     -- so once past this gate, an ordinary tenant-scoped query for a
         *     resource that doesn't exist in this store naturally 404s via
         *     `DoesNotExist`, with no separate leak to worry about.
         *
         *     Sets `self.store` for subclasses to use.
         */
        get: operations["api_v1_dashboard_stores_tags_retrieve"];
        put?: never;
        /**
         * @description Base class for any `/api/v1/dashboard/stores/<uuid:store_id>/...`
         *     endpoint. Relies on `TenantMiddleware` having already resolved the
         *     path's `store_id` into `request.tenant_store` (path-based, Host
         *     header ignored -- apps/stores/middleware.py).
         *
         *     404 vs 403 distinguished on purpose (same reasoning as Phase 3's
         *     StoreDetailView, docs/PHASE_3_REPORT.md): a store's existence isn't
         *     secret (its RLS SELECT policy is intentionally open), but catalog
         *     resources INSIDE it are fully RLS-restricted with no such exception
         *     -- so once past this gate, an ordinary tenant-scoped query for a
         *     resource that doesn't exist in this store naturally 404s via
         *     `DoesNotExist`, with no separate leak to worry about.
         *
         *     Sets `self.store` for subclasses to use.
         */
        post: operations["api_v1_dashboard_stores_tags_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dashboard/stores/{store_id}/theme": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * @description Base class for any `/api/v1/dashboard/stores/<uuid:store_id>/...`
         *     endpoint. Relies on `TenantMiddleware` having already resolved the
         *     path's `store_id` into `request.tenant_store` (path-based, Host
         *     header ignored -- apps/stores/middleware.py).
         *
         *     404 vs 403 distinguished on purpose (same reasoning as Phase 3's
         *     StoreDetailView, docs/PHASE_3_REPORT.md): a store's existence isn't
         *     secret (its RLS SELECT policy is intentionally open), but catalog
         *     resources INSIDE it are fully RLS-restricted with no such exception
         *     -- so once past this gate, an ordinary tenant-scoped query for a
         *     resource that doesn't exist in this store naturally 404s via
         *     `DoesNotExist`, with no separate leak to worry about.
         *
         *     Sets `self.store` for subclasses to use.
         */
        get: operations["api_v1_dashboard_stores_theme_retrieve"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dashboard/theme-presets": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["api_v1_dashboard_theme_presets_list"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/audit-logs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["api_v1_platform_audit_logs_list"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/overview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["api_v1_platform_overview_retrieve"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/plans": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["api_v1_platform_plans_list"];
        put?: never;
        post: operations["api_v1_platform_plans_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/plans/{plan_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["api_v1_platform_plans_retrieve"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/plans/{plan_id}/activate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post: operations["api_v1_platform_plans_activate_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/plans/{plan_id}/deactivate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post: operations["api_v1_platform_plans_deactivate_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/plans/{plan_id}/versions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post: operations["api_v1_platform_plans_versions_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/stores": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["api_v1_platform_stores_list"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/stores/{store_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["api_v1_platform_stores_retrieve"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/stores/{store_id}/activate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post: operations["api_v1_platform_stores_activate_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/stores/{store_id}/suspend": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post: operations["api_v1_platform_stores_suspend_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/subscriptions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["api_v1_platform_subscriptions_list"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/subscriptions/{subscription_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["api_v1_platform_subscriptions_retrieve"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/subscriptions/{subscription_id}/activate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post: operations["api_v1_platform_subscriptions_activate_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/subscriptions/{subscription_id}/cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post: operations["api_v1_platform_subscriptions_cancel_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/users": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["api_v1_platform_users_list"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/users/{user_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["api_v1_platform_users_retrieve"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/platform/users/{user_id}/mfa/reset": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * @description Explicit, audited privileged action -- see
         *     `services.reset_user_mfa`'s docstring for why this exists instead of
         *     any self-service MFA bypass.
         */
        post: operations["api_v1_platform_users_mfa_reset_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/storefront/cart": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description Resolves/creates `self.cart` from the cart cookie, setting it on the way out if it's new. */
        get: operations["api_v1_storefront_cart_retrieve"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/storefront/cart/coupon": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** @description Resolves/creates `self.cart` from the cart cookie, setting it on the way out if it's new. */
        post: operations["api_v1_storefront_cart_coupon_create"];
        /** @description Resolves/creates `self.cart` from the cart cookie, setting it on the way out if it's new. */
        delete: operations["api_v1_storefront_cart_coupon_destroy"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/storefront/cart/items": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** @description Resolves/creates `self.cart` from the cart cookie, setting it on the way out if it's new. */
        post: operations["api_v1_storefront_cart_items_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/storefront/cart/items/{item_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** @description Resolves/creates `self.cart` from the cart cookie, setting it on the way out if it's new. */
        delete: operations["api_v1_storefront_cart_items_destroy"];
        options?: never;
        head?: never;
        /** @description Resolves/creates `self.cart` from the cart cookie, setting it on the way out if it's new. */
        patch: operations["api_v1_storefront_cart_items_partial_update"];
        trace?: never;
    };
    "/api/v1/storefront/cart/reprice": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** @description Resolves/creates `self.cart` from the cart cookie, setting it on the way out if it's new. */
        post: operations["api_v1_storefront_cart_reprice_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/storefront/cart/shipping-quotes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * @description Informational only -- see apps/shipping/models.py's module docstring
         *     (scope decision 2). Never a checkout prerequisite: nothing here is
         *     persisted onto the cart, and Phase 8's Order creation path must
         *     independently re-price shipping at authoritative checkout time
         *     (see docs/PHASE_6_REPORT.md's mandatory Phase 8 rule).
         */
        get: operations["api_v1_storefront_cart_shipping_quotes_list"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/storefront/categories": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * @description Base class for any `/api/v1/storefront/...` endpoint. Relies on
         *     `TenantMiddleware` having resolved the request's Host header into
         *     `request.tenant_store` (apps/stores/middleware.py) -- deliberately
         *     the OPPOSITE resolution path from `StoreScopedAPIView` (Host, never
         *     a path segment), matching how a real storefront request arrives
         *     (`store1.example.com`, not `/dashboard/stores/<id>/...`).
         *
         *     Public/guest-accessible by design (`AllowAny`) -- storefront
         *     endpoints serve shoppers, not authenticated merchant staff. No
         *     unresolved-host case is silently allowed through: an unknown
         *     hostname 404s here, same as a genuinely nonexistent dashboard store.
         *
         *     Sets `self.store` for subclasses to use.
         */
        get: operations["api_v1_storefront_categories_list"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/storefront/checkout/address": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** @description Resolves/creates `self.cart` from the cart cookie, setting it on the way out if it's new. */
        post: operations["api_v1_storefront_checkout_address_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/storefront/checkout/complete": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** @description Resolves/creates `self.cart` from the cart cookie, setting it on the way out if it's new. */
        post: operations["api_v1_storefront_checkout_complete_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/storefront/checkout/shipping": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** @description Resolves/creates `self.cart` from the cart cookie, setting it on the way out if it's new. */
        post: operations["api_v1_storefront_checkout_shipping_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/storefront/checkout/start": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** @description Resolves/creates `self.cart` from the cart cookie, setting it on the way out if it's new. */
        post: operations["api_v1_storefront_checkout_start_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/storefront/context": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * @description Phase 13: `GET /api/v1/storefront/context` -- the one call every
         *     storefront page needs before it can render anything (which store,
         *     which theme, which settings). Host-resolved like every other
         *     storefront endpoint; see `StorefrontAPIView`.
         */
        get: operations["api_v1_storefront_context_retrieve"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/storefront/inventory/availability": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * @description `GET .../storefront/inventory/availability?variant=<id>&variant=<id>` --
         *     Phase 13. Only ever returns a summed "available across all locations"
         *     integer per variant, never per-location detail or any other
         *     `StockBalance` field -- that breakdown is a merchant-only concept.
         *     An id with no `StockBalance` rows at all is simply absent from the
         *     response (zero-available and never-stocked look the same to a
         *     shopper: not orderable).
         */
        get: operations["api_v1_storefront_inventory_availability_retrieve"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/storefront/payments/initiate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * @description Base class for any `/api/v1/storefront/...` endpoint. Relies on
         *     `TenantMiddleware` having resolved the request's Host header into
         *     `request.tenant_store` (apps/stores/middleware.py) -- deliberately
         *     the OPPOSITE resolution path from `StoreScopedAPIView` (Host, never
         *     a path segment), matching how a real storefront request arrives
         *     (`store1.example.com`, not `/dashboard/stores/<id>/...`).
         *
         *     Public/guest-accessible by design (`AllowAny`) -- storefront
         *     endpoints serve shoppers, not authenticated merchant staff. No
         *     unresolved-host case is silently allowed through: an unknown
         *     hostname 404s here, same as a genuinely nonexistent dashboard store.
         *
         *     Sets `self.store` for subclasses to use.
         */
        post: operations["api_v1_storefront_payments_initiate_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/storefront/payments/providers": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * @description `GET /api/v1/storefront/payments/providers` -- Phase 13's checkout
         *     payment-method picker. Only enabled providers, only `provider_key`.
         */
        get: operations["api_v1_storefront_payments_providers_list"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/storefront/products": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * @description Base class for any `/api/v1/storefront/...` endpoint. Relies on
         *     `TenantMiddleware` having resolved the request's Host header into
         *     `request.tenant_store` (apps/stores/middleware.py) -- deliberately
         *     the OPPOSITE resolution path from `StoreScopedAPIView` (Host, never
         *     a path segment), matching how a real storefront request arrives
         *     (`store1.example.com`, not `/dashboard/stores/<id>/...`).
         *
         *     Public/guest-accessible by design (`AllowAny`) -- storefront
         *     endpoints serve shoppers, not authenticated merchant staff. No
         *     unresolved-host case is silently allowed through: an unknown
         *     hostname 404s here, same as a genuinely nonexistent dashboard store.
         *
         *     Sets `self.store` for subclasses to use.
         */
        get: operations["api_v1_storefront_products_list"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/storefront/products/{slug}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * @description Base class for any `/api/v1/storefront/...` endpoint. Relies on
         *     `TenantMiddleware` having resolved the request's Host header into
         *     `request.tenant_store` (apps/stores/middleware.py) -- deliberately
         *     the OPPOSITE resolution path from `StoreScopedAPIView` (Host, never
         *     a path segment), matching how a real storefront request arrives
         *     (`store1.example.com`, not `/dashboard/stores/<id>/...`).
         *
         *     Public/guest-accessible by design (`AllowAny`) -- storefront
         *     endpoints serve shoppers, not authenticated merchant staff. No
         *     unresolved-host case is silently allowed through: an unknown
         *     hostname 404s here, same as a genuinely nonexistent dashboard store.
         *
         *     Sets `self.store` for subclasses to use.
         */
        get: operations["api_v1_storefront_products_retrieve"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/subscriptions/billing/webhook": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * @description Phase E's real webhook endpoint -- the same idempotent,
         *     state-guarded `billing.apply_payment_event` this app's own demo-
         *     provider-simulation Celery task calls, reachable over HTTP the way
         *     a genuine provider callback would arrive. Deliberately `AllowAny`
         *     (a real webhook is never an authenticated user session) but hard-
         *     gated to `SUBSCRIPTION_BILLING_MODE == "demo"` -- there is no
         *     "live" signature verification implemented yet (see
         *     `apps.payments.services.process_webhook` for what that eventually
         *     needs to look like), so this must never be reachable in production
         *     regardless of URL discovery.
         */
        post: operations["api_v1_subscriptions_billing_webhook_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/subscriptions/checkout-sessions/current": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * @description Phase D: the authenticated user's own in-progress checkout
         *     session, always resolved by `request.user` -- never a client-held
         *     session id (see `SubscriptionCheckoutSession`'s own docstring on
         *     why: the choice must survive a refresh or a fresh login exactly
         *     the same way, which a client-stored id could not guarantee if it
         *     were ever lost).
         *
         *     GET returns the current session or 404 if none exists yet (a
         *     visitor who has picked neither a theme nor a plan). POST starts one
         *     (or updates the theme on an existing one) -- the marketplace's
         *     "Use this theme" flow. PATCH selects a plan on the existing session
         *     -- server-validated against real Plan/PlanVersion data, per
         *     `apps.subscriptions.services.select_plan_for_checkout_session`;
         *     the request body is a plan_version_id ONLY, never a price.
         */
        get: operations["api_v1_subscriptions_checkout_sessions_current_retrieve"];
        put?: never;
        /**
         * @description Phase D: the authenticated user's own in-progress checkout
         *     session, always resolved by `request.user` -- never a client-held
         *     session id (see `SubscriptionCheckoutSession`'s own docstring on
         *     why: the choice must survive a refresh or a fresh login exactly
         *     the same way, which a client-stored id could not guarantee if it
         *     were ever lost).
         *
         *     GET returns the current session or 404 if none exists yet (a
         *     visitor who has picked neither a theme nor a plan). POST starts one
         *     (or updates the theme on an existing one) -- the marketplace's
         *     "Use this theme" flow. PATCH selects a plan on the existing session
         *     -- server-validated against real Plan/PlanVersion data, per
         *     `apps.subscriptions.services.select_plan_for_checkout_session`;
         *     the request body is a plan_version_id ONLY, never a price.
         */
        post: operations["api_v1_subscriptions_checkout_sessions_current_create"];
        delete?: never;
        options?: never;
        head?: never;
        /**
         * @description Phase D: the authenticated user's own in-progress checkout
         *     session, always resolved by `request.user` -- never a client-held
         *     session id (see `SubscriptionCheckoutSession`'s own docstring on
         *     why: the choice must survive a refresh or a fresh login exactly
         *     the same way, which a client-stored id could not guarantee if it
         *     were ever lost).
         *
         *     GET returns the current session or 404 if none exists yet (a
         *     visitor who has picked neither a theme nor a plan). POST starts one
         *     (or updates the theme on an existing one) -- the marketplace's
         *     "Use this theme" flow. PATCH selects a plan on the existing session
         *     -- server-validated against real Plan/PlanVersion data, per
         *     `apps.subscriptions.services.select_plan_for_checkout_session`;
         *     the request body is a plan_version_id ONLY, never a price.
         */
        patch: operations["api_v1_subscriptions_checkout_sessions_current_partial_update"];
        trace?: never;
    };
    "/api/v1/subscriptions/checkout-sessions/current/business-info": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * @description Phase F: the step that actually creates the Store. Requires a
         *     session already in `awaiting_business_info` (see
         *     `CheckoutSessionPayView`) -- `contact_email` is always
         *     `request.user.email`, never accepted from the client.
         */
        post: operations["api_v1_subscriptions_checkout_sessions_current_business_info_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/subscriptions/checkout-sessions/current/pay": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * @description Phase E: starts (or retries) a real, sandbox-provider-backed
         *     payment attempt -- gated by `settings.SUBSCRIPTION_BILLING_MODE`
         *     (see that setting's comment in config/settings/base.py). Creates a
         *     `SubscriptionPaymentIntent` and moves the session to
         *     `payment_pending`; the intent resolves asynchronously (a Celery task
         *     simulating the provider's own pending -> processing -> succeeded/
         *     failed callback, processed through the exact same idempotent
         *     webhook-handling code a real provider's callback would use -- see
         *     `apps.subscriptions.billing`). Never creates a Store.
         */
        post: operations["api_v1_subscriptions_checkout_sessions_current_pay_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/subscriptions/checkout-sessions/current/payment-intent": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * @description Phase E: the authenticated user's most recent payment intent --
         *     polled by the checkout page while `state` is pending/processing,
         *     read once more for `failure_reason` on the failure screen. Scoped
         *     by `request.user` only, same "server-side, never a client-held id"
         *     posture as `CheckoutSessionCurrentView`.
         */
        get: operations["api_v1_subscriptions_checkout_sessions_current_payment_intent_retrieve"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/subscriptions/checkout-sessions/current/skip-payment-demo": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * @description DEMO-ONLY testing convenience, requested explicitly to speed up
         *     manual walkthroughs of the checkout flow: reaches
         *     `awaiting_business_info` without filling in the card form. Goes
         *     through the exact same state machine and idempotent
         *     `apply_payment_event` a real payment does (see
         *     `billing.skip_payment_demo`'s own docstring) -- this is NOT a
         *     bypass of Phase E's payment gate, it's a same-shaped payment that
         *     always succeeds synchronously instead of asynchronously. Gated by
         *     `SUBSCRIPTION_BILLING_MODE` exactly like `InitiatePaymentView`, so
         *     it is unreachable in production the same way.
         */
        post: operations["api_v1_subscriptions_checkout_sessions_current_skip_payment_demo_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/subscriptions/plans/public": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * @description Phase D: the plan-selection screen's data source. Genuinely
         *     unauthenticated (`AllowAny`), matching `apps.themes`'s public
         *     theme-preset endpoints -- Plan/PlanVersion already carry an open
         *     RLS SELECT policy for everyone (Phase 10, approved architecture
         *     decision 1), so exposing the current public plans over HTTP adds
         *     no new write surface and leaks nothing merchant-specific.
         */
        get: operations["api_v1_subscriptions_plans_public_list"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/themes/public/presets": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * @description Phase B: the public theme marketplace's data source. Genuinely
         *     unauthenticated (`AllowAny`) -- the whole point of the marketplace
         *     is that a visitor browses it BEFORE registering. Read-only,
         *     platform-global, RLS-readonly data (same `Theme`/`ThemeVersion`/
         *     `ThemePreset` rows `ThemePresetListView` already serves to
         *     authenticated onboarding) -- exposing it publicly adds no new
         *     write surface and leaks nothing merchant-specific.
         */
        get: operations["api_v1_themes_public_presets_list"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/themes/public/presets/{preset_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * @description One preset's full data for the public preview page -- same
         *     access rules as the list view above.
         */
        get: operations["api_v1_themes_public_presets_retrieve"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/webhooks/payments/{provider}/{store_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * @description Base class for `/api/v1/webhooks/payments/<provider>/<uuid:store_id>`
         *     (Phase 9) -- the third tenant-resolution strategy, added to
         *     `TenantMiddleware` alongside dashboard/storefront (see that module's
         *     docstring). No Host to trust, no authenticated user to check
         *     membership for (`AllowAny`, same reasoning as `StorefrontAPIView`) --
         *     the store_id path segment ONLY resolves which tenant's RLS scope to
         *     look the provider config up in. It is never treated as a security
         *     boundary by itself: `apps.payments.services.process_webhook` still
         *     verifies the provider's signature before any side effect, exactly as
         *     it would for a forged store_id pointing at a real store.
         *
         *     Sets `self.store` for subclasses to use.
         */
        post: operations["api_v1_webhooks_payments_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        AddCartItemRequest: {
            /** Format: uuid */
            variant: string;
            quantity: number;
        };
        AdjustStockRequest: {
            /** Format: uuid */
            variant: string;
            /** Format: uuid */
            location: string;
            delta: number;
            reason: string;
            /** @default  */
            reference: string;
        };
        ApplyCouponRequest: {
            code: string;
        };
        AuditLog: {
            /** Format: uuid */
            readonly id: string;
            /** Format: uuid */
            readonly actor_user_id: string;
            /**
             * Format: email
             * @description Denormalized at write time -- readable without a second cross-role join, and stable even if the actor account is later renamed.
             */
            readonly actor_email: string;
            readonly action: string;
            readonly target_type: string;
            /** Format: uuid */
            readonly target_id: string;
            /** Format: uuid */
            readonly store_id: string | null;
            /** @description Safe, non-secret context only -- never tokens/passwords/payment data. */
            readonly metadata: unknown;
            /** Format: date-time */
            readonly created_at: string;
        };
        /**
         * @description * `monthly` - Monthly
         *     * `yearly` - Yearly
         * @enum {string}
         */
        BillingIntervalEnum: "monthly" | "yearly";
        /**
         * @description Phase F. Multipart (the request carries a real file for `logo`).
         *     `contact_email` is deliberately NOT a field here -- it is always the
         *     authenticated user's own account email, taken server-side in the
         *     view, never accepted from the client (see
         *     apps.subscriptions.services.complete_checkout_with_business_info's
         *     docstring).
         */
        BusinessInfoRequest: {
            store_name: string;
            business_category: string;
            contact_phone: string;
            /** Format: binary */
            logo?: string | null;
        };
        Cart: {
            /** Format: uuid */
            readonly id: string;
            readonly status: components["schemas"]["CartStatusEnum"];
            readonly currency: string;
            readonly items: components["schemas"]["CartItem"][];
            readonly coupon_code: string;
            readonly subtotal_amount: number;
            readonly discount_amount: number;
            readonly tax_amount: number;
            readonly total_amount: number;
        };
        CartItem: {
            /** Format: uuid */
            readonly id: string;
            /** Format: uuid */
            variant: string;
            readonly variant_sku: string;
            readonly product_name: string;
            readonly product_slug: string;
            quantity: number;
            readonly unit_price_amount: number;
            readonly currency: string;
        };
        /**
         * @description * `active` - Active
         *     * `abandoned` - Abandoned
         * @enum {string}
         */
        CartStatusEnum: "active" | "abandoned";
        CheckoutAddressRequestRequest: {
            /** Format: email */
            email: string;
            shipping_address: components["schemas"]["ShippingAddressRequest"];
        };
        CheckoutSession: {
            /** Format: uuid */
            id: string;
            status: string;
            /** Format: date-time */
            expires_at: string;
            /** Format: email */
            email: string;
            shipping_address: unknown;
            /** Format: uuid */
            shipping_method_id: string | null;
            shipping_method_name_snapshot: string;
            shipping_amount_snapshot: number | null;
        };
        CheckoutShippingRequestRequest: {
            /** Format: uuid */
            shipping_method_id: string;
        };
        /**
         * @description * `draft` - Draft
         *     * `ready_for_payment` - Ready for payment
         *     * `payment_pending` - Payment pending
         *     * `payment_failed` - Payment failed
         *     * `awaiting_business_info` - Awaiting business info
         *     * `completed` - Completed
         *     * `abandoned` - Abandoned
         *     * `expired` - Expired
         * @enum {string}
         */
        CheckoutStatusEnum: "draft" | "ready_for_payment" | "payment_pending" | "payment_failed" | "awaiting_business_info" | "completed" | "abandoned" | "expired";
        /** @description One-shot: Product + its default variant -- see apps/catalog/services.py:create_product. */
        CreateProductRequest: {
            name: string;
            slug: string;
            /** @default  */
            description: string;
            /** @default  */
            seo_title: string;
            /** @default  */
            seo_description: string;
            sku: string;
            price_amount: number;
            currency?: string;
        };
        CreateStoreRequest: {
            name: string;
            slug: string;
            /** Format: uuid */
            theme_preset_id?: string | null;
        };
        /**
         * @description Minimal response for the business-info step -- just enough for
         *     the frontend to redirect straight to the new Store's dashboard.
         */
        CreatedStore: {
            /** Format: uuid */
            readonly id: string;
            readonly name: string;
            readonly slug: string;
        };
        /**
         * @description * `unfulfilled` - Unfulfilled
         * @enum {string}
         */
        FulfillmentStatusEnum: "unfulfilled";
        /**
         * @description Phase E. `card_number` is NEVER persisted (see
         *     `SubscriptionPaymentIntent` -- no card-data field exists on it at
         *     all) -- used only by `apps.subscriptions.billing.simulate_demo_outcome`
         *     to pick which demo outcome fires. Not validated as a real card
         *     number (Luhn, length, etc.) on purpose -- this is a sandbox
         *     convention (Stripe-test-number-style), not a real payment field.
         */
        InitiatePaymentRequest: {
            card_number: string;
        };
        /**
         * @description * `flat` - Flat rate
         *     * `free` - Free shipping
         *     * `weight_based` - Weight based
         *     * `price_based` - Order value based
         *     * `carrier_calculated` - Carrier calculated
         * @enum {string}
         */
        KindEnum: "flat" | "free" | "weight_based" | "price_based" | "carrier_calculated";
        /**
         * @description * `test` - Test
         *     * `live` - Live
         * @enum {string}
         */
        ModeEnum: "test" | "live";
        Order: {
            /** Format: uuid */
            readonly id: string;
            number: string;
            /** Format: email */
            email: string;
            status?: components["schemas"]["Status206Enum"];
            fulfillment_status?: components["schemas"]["FulfillmentStatusEnum"];
            currency: string;
            subtotal_amount: number;
            discount_amount: number;
            tax_amount: number;
            shipping_amount: number;
            total_amount: number;
            shipping_address: unknown;
            shipping_method_name_snapshot: string;
            coupon_code_snapshot?: string;
            /** Format: date-time */
            readonly created_at: string;
            readonly items: components["schemas"]["OrderItem"][];
        };
        OrderItem: {
            /** Format: uuid */
            readonly id: string;
            variant_name_snapshot: string;
            variant_sku_snapshot: string;
            variant_options_snapshot?: unknown;
            unit_price_amount: number;
            quantity: number;
            currency: string;
            readonly line_total_amount: number;
        };
        /** @description Dashboard list view -- no `items` (avoids N+1 across a page of orders). */
        OrderList: {
            /** Format: uuid */
            readonly id: string;
            number: string;
            /** Format: email */
            email: string;
            status?: components["schemas"]["Status206Enum"];
            fulfillment_status?: components["schemas"]["FulfillmentStatusEnum"];
            currency: string;
            total_amount: number;
            /** Format: date-time */
            readonly created_at: string;
        };
        PatchedSelectPlanRequest: {
            /** Format: uuid */
            plan_version_id?: string;
        };
        PatchedUpdateCartItemRequest: {
            quantity?: number;
        };
        PatchedUpdateProductRequest: {
            name?: string;
            slug?: string;
            description?: string;
            status?: components["schemas"]["StatusA5eEnum"];
            seo_title?: string;
            seo_description?: string;
        };
        /**
         * @description PATCH surface for store settings (Phase 12). Deliberately narrow:
         *     only fields Store itself already authoritatively owns --
         *     `status` is excluded (subscription-lifecycle-managed, see
         *     apps.subscriptions.tasks, never merchant-settable directly), and
         *     nothing here touches StoreDomain/StoreThemeConfig, which have their
         *     own owners.
         */
        PatchedUpdateStoreRequest: {
            name?: string;
            slug?: string;
            default_currency?: string;
            /** Format: email */
            contact_email?: string;
            contact_phone?: string;
        };
        PaymentInitiateRequestRequest: {
            /** Format: uuid */
            order_id: string;
            provider_key: components["schemas"]["ProviderKeyEnum"];
        };
        /**
         * @description Documents the exact plain-dict shape `apps.payments.services._intent_body`
         *     already returns -- for `@extend_schema` typing only, never constructed
         *     or validated against directly (the view returns the service's dict as-is).
         */
        PaymentIntentResponse: {
            /** Format: uuid */
            id: string;
            /** Format: uuid */
            order_id: string;
            state: string;
            amount: number;
            currency: string;
            provider_key: string;
        };
        /**
         * @description * `not_started` - Not started
         *     * `pending` - Pending
         *     * `paid` - Paid
         *     * `failed` - Failed
         * @enum {string}
         */
        PaymentStatusEnum: "not_started" | "pending" | "paid" | "failed";
        Plan: {
            /** Format: uuid */
            readonly id: string;
            readonly code: string;
            readonly name: string;
            readonly is_public: boolean;
            readonly trial_days: number;
            readonly grace_period_days: number;
            readonly is_default_trial: boolean;
            /** Format: date-time */
            readonly created_at: string;
        };
        PlanCreateRequestRequest: {
            code: string;
            name: string;
            /** @default true */
            is_public: boolean;
            /** @default 0 */
            trial_days: number;
            /** @default 3 */
            grace_period_days: number;
        };
        /**
         * @description `versions` is populated explicitly by the view (a separate,
         *     correctly-ordered `list_plan_versions` call), not by DRF resolving
         *     `plan.versions` as a related manager -- see
         *     apps.platform_admin.views.PlatformPlanDetailView.
         */
        PlanDetail: {
            /** Format: uuid */
            readonly id: string;
            readonly code: string;
            readonly name: string;
            readonly is_public: boolean;
            readonly trial_days: number;
            readonly grace_period_days: number;
            readonly is_default_trial: boolean;
            /** Format: date-time */
            readonly created_at: string;
            readonly versions: components["schemas"]["PlanVersion"][];
        };
        PlanVersion: {
            /** Format: uuid */
            readonly id: string;
            readonly version_number: number;
            readonly price_monthly: number;
            readonly price_yearly: number;
            readonly currency: string;
            readonly is_current: boolean;
            /** Format: date-time */
            readonly published_at: string;
            readonly features: components["schemas"]["PlanVersionFeature"][];
            readonly quotas: components["schemas"]["PlanVersionQuota"][];
        };
        PlanVersionFeature: {
            feature_key: string;
            enabled?: boolean;
        };
        PlanVersionPublishRequestRequest: {
            price_monthly: number;
            price_yearly: number;
            /** @default SAR */
            currency: string;
            features?: {
                [key: string]: boolean;
            };
            quotas?: {
                [key: string]: number | null;
            };
            /** @default true */
            make_current: boolean;
        };
        PlanVersionQuota: {
            quota_key: string;
            limit?: number | null;
        };
        PlatformStore: {
            /** Format: uuid */
            readonly id: string;
            readonly name: string;
            readonly slug: string;
            readonly status: components["schemas"]["StatusBb6Enum"];
            readonly default_currency: string;
            /** Format: email */
            readonly contact_email: string;
            readonly contact_phone: string;
            /** Format: date-time */
            readonly created_at: string;
        };
        PlatformTokenObtainPairRequest: {
            email: string;
            password: string;
        };
        PlatformTokenRefresh: {
            refresh: string;
            readonly access: string;
        };
        PlatformTokenRefreshRequest: {
            refresh: string;
        };
        PlatformUser: {
            /** Format: uuid */
            readonly id: string;
            /** Format: email */
            readonly email: string;
            readonly full_name: string;
            readonly is_active: boolean;
            /** @description Platform Owner realm staff -- see apps.platform_admin (Phase 14). */
            readonly is_platform_staff: boolean;
            /** Format: date-time */
            readonly email_verified_at: string | null;
            /** Format: date-time */
            readonly created_at: string;
        };
        /**
         * @description * `margin_percent` - Margin %
         *     * `markup_percent` - Markup %
         *     * `fixed` - Fixed price
         * @enum {string}
         */
        PricingStrategyEnum: "margin_percent" | "markup_percent" | "fixed";
        Product: {
            /** Format: uuid */
            readonly id: string;
            name: string;
            slug: string;
            description?: string;
            status?: components["schemas"]["StatusA5eEnum"];
            seo_title?: string;
            seo_description?: string;
            readonly options: components["schemas"]["ProductOption"][];
            readonly variants: components["schemas"]["ProductVariant"][];
            /** Format: date-time */
            readonly created_at: string;
            /** Format: date-time */
            readonly updated_at: string;
        };
        ProductOption: {
            /** Format: uuid */
            readonly id: string;
            name: string;
            readonly position: number;
            readonly values: components["schemas"]["ProductOptionValue"][];
        };
        ProductOptionValue: {
            /** Format: uuid */
            readonly id: string;
            value: string;
            readonly position: number;
        };
        ProductVariant: {
            /** Format: uuid */
            readonly id: string;
            sku: string;
            status?: components["schemas"]["ProductVariantStatusEnum"];
            /** @description True only for the auto-created variant of a simple (option-less) product. */
            readonly is_default: boolean;
            readonly position: number;
            currency: string;
            price_amount: number;
            compare_at_price_amount?: number | null;
            cost_price_amount?: number | null;
            weight_grams?: number | null;
            length_mm?: number | null;
            width_mm?: number | null;
            height_mm?: number | null;
            barcode?: string;
            readonly option_values: components["schemas"]["VariantOptionValue"][];
        };
        /**
         * @description * `active` - Active
         *     * `archived` - Archived
         * @enum {string}
         */
        ProductVariantStatusEnum: "active" | "archived";
        PromoteRequestRequest: {
            name: string;
            slug: string;
            sku: string;
            price_amount: number;
            /** Format: uuid */
            location_id?: string | null;
            initial_stock?: number | null;
        };
        /**
         * @description * `mock` - Mock (demo data)
         * @enum {string}
         */
        ProviderEnum: "mock";
        /**
         * @description * `mock` - mock
         *     * `manual_cod` - manual_cod
         *     * `stripe` - stripe
         * @enum {string}
         */
        ProviderKeyEnum: "mock" | "manual_cod" | "stripe";
        /**
         * @description * `not_started` - Not started
         *     * `pending` - Pending
         *     * `provisioning` - Provisioning
         *     * `provisioned` - Provisioned
         *     * `failed` - Failed
         * @enum {string}
         */
        ProvisioningStatusEnum: "not_started" | "pending" | "provisioning" | "provisioned" | "failed";
        /**
         * @description Phase D: the public/authenticated plan-selection screen's data
         *     source. Real, dynamic PlanVersion data -- price/features/quotas
         *     are read straight off the DB row the platform admin (via
         *     `publish_plan_version`/a seed migration) actually published, never
         *     a value the frontend invents. `features`/`quotas` are nested lists
         *     (not a single JSON blob) so the frontend can render a real
         *     checklist without guessing key meanings client-side.
         */
        PublicPlanVersion: {
            /** Format: uuid */
            readonly id: string;
            readonly plan_code: string;
            readonly plan_name: string;
            readonly price_monthly: number;
            readonly price_yearly: number;
            readonly currency: string;
            readonly features: components["schemas"]["PlanVersionFeature"][];
            readonly quotas: components["schemas"]["PlanVersionQuota"][];
        };
        /**
         * @description The public marketplace's card shape -- adds `theme_name`/
         *     `theme_category` (never needed by the authenticated onboarding
         *     picker, which already knows which theme it's showing) on top of
         *     `ThemePresetSerializer`'s fields. A deliberately separate
         *     serializer, not a superset flag on the same one: the two endpoints
         *     have different audiences (anonymous visitor vs. an authenticated
         *     merchant mid-onboarding) and should be free to diverge.
         */
        PublicThemePreset: {
            /** Format: uuid */
            readonly id: string;
            readonly name: string;
            readonly default_settings: unknown;
            /** Format: uri */
            readonly preview_image_url: string;
            readonly theme_code: string;
            readonly theme_name: string;
            readonly theme_category: string;
        };
        /**
         * @description Validated JSONB snapshot shape -- see apps/orders/models.py's module docstring,
         *     decision 4 (no `CustomerAddress` model in Phase 8).
         */
        ShippingAddressRequest: {
            recipient_name: string;
            phone: string;
            country_code: string;
            /** @default  */
            region: string;
            city: string;
            /** @default  */
            postal_code: string;
            line1: string;
            /** @default  */
            line2: string;
        };
        ShippingMethod: {
            /** Format: uuid */
            readonly id: string;
            /** Format: uuid */
            zone: string;
            name: string;
            kind: components["schemas"]["KindEnum"];
            is_active?: boolean;
            position?: number;
        };
        ShippingMethodRequest: {
            /** Format: uuid */
            zone: string;
            name: string;
            kind: components["schemas"]["KindEnum"];
            is_active?: boolean;
            position?: number;
        };
        ShippingQuote: {
            /** Format: uuid */
            method_id: string;
            method_name: string;
            kind: string;
            price_amount: number;
            currency: string;
        };
        ShippingRate: {
            /** Format: uuid */
            readonly id: string;
            /** Format: uuid */
            method: string;
            min_value?: number | null;
            max_value?: number | null;
            price_amount: number;
            currency: string;
        };
        ShippingRateRequest: {
            /** Format: uuid */
            method: string;
            min_value?: number | null;
            max_value?: number | null;
            price_amount: number;
            currency: string;
        };
        ShippingZone: {
            /** Format: uuid */
            readonly id: string;
            name: string;
            /** @description ISO 3166-1 alpha-2 codes. Empty means 'matches any country' (a catch-all zone). */
            countries?: string[];
            regions?: string[];
            /** @description Postal-code PREFIXES (e.g. '11' matches any code starting with '11'). */
            postal_patterns?: string[];
            priority?: number;
            is_active?: boolean;
        };
        ShippingZoneRequest: {
            name: string;
            /** @description ISO 3166-1 alpha-2 codes. Empty means 'matches any country' (a catch-all zone). */
            countries?: string[];
            regions?: string[];
            /** @description Postal-code PREFIXES (e.g. '11' matches any code starting with '11'). */
            postal_patterns?: string[];
            priority?: number;
            is_active?: boolean;
        };
        StartSubscriptionCheckoutSessionRequest: {
            /** Format: uuid */
            theme_preset_id?: string | null;
        };
        /**
         * @description * `pending` - Pending
         *     * `processing` - Processing
         *     * `succeeded` - Succeeded
         *     * `failed` - Failed
         *     * `cancelled` - Cancelled
         * @enum {string}
         */
        StateEnum: "pending" | "processing" | "succeeded" | "failed" | "cancelled";
        /**
         * @description * `pending_payment` - Pending payment
         *     * `confirmed` - Confirmed
         *     * `cancelled` - Cancelled
         * @enum {string}
         */
        Status206Enum: "pending_payment" | "confirmed" | "cancelled";
        /**
         * @description * `trialing` - Trialing
         *     * `active` - Active
         *     * `past_due` - Past due
         *     * `canceled` - Canceled
         * @enum {string}
         */
        Status3a5Enum: "trialing" | "active" | "past_due" | "canceled";
        /**
         * @description * `draft` - Draft
         *     * `active` - Active
         *     * `archived` - Archived
         * @enum {string}
         */
        StatusA5eEnum: "draft" | "active" | "archived";
        /**
         * @description * `pending` - Pending
         *     * `active` - Active
         *     * `suspended` - Suspended
         *     * `closed` - Closed
         *     * `read_only` - Read-only
         * @enum {string}
         */
        StatusBb6Enum: "pending" | "active" | "suspended" | "closed" | "read_only";
        StockBalance: {
            /** Format: uuid */
            readonly id: string;
            /** Format: uuid */
            variant: string;
            readonly variant_sku: string;
            /** Format: uuid */
            location: string;
            readonly location_name: string;
            readonly quantity_on_hand: number;
            readonly quantity_reserved: number;
            readonly quantity_available: number;
            low_stock_threshold?: number | null;
            readonly is_low_stock: boolean;
        };
        StockLocation: {
            /** Format: uuid */
            readonly id: string;
            name: string;
            is_active?: boolean;
        };
        StockLocationRequest: {
            name: string;
            is_active?: boolean;
        };
        StoreDetail: {
            /** Format: uuid */
            readonly id: string;
            readonly name: string;
            readonly slug: string;
            readonly status: components["schemas"]["StatusBb6Enum"];
            readonly default_currency: string;
            /** Format: email */
            readonly contact_email: string;
            readonly contact_phone: string;
            readonly logo: string | null;
            /** Format: date-time */
            readonly created_at: string;
        };
        StoreListItem: {
            /** Format: uuid */
            readonly id: string;
            readonly name: string;
            readonly slug: string;
            readonly status: components["schemas"]["StatusBb6Enum"];
            readonly logo: string | null;
        };
        /**
         * @description `credentials`/`webhook_secret` are write-only (docs/ARCHITECTURE.md section
         *     8.3: "لا endpoint يعيد السر إطلاقًا") -- never round-tripped back out. Reading
         *     a config only ever shows `credentials_hint`, computed once at write time.
         */
        StoreProviderConfig: {
            /** Format: uuid */
            readonly id: string;
            provider_key: string;
            mode?: components["schemas"]["ModeEnum"];
            is_enabled?: boolean;
            readonly credentials_hint: string;
            public_metadata?: unknown;
        };
        /**
         * @description `credentials`/`webhook_secret` are write-only (docs/ARCHITECTURE.md section
         *     8.3: "لا endpoint يعيد السر إطلاقًا") -- never round-tripped back out. Reading
         *     a config only ever shows `credentials_hint`, computed once at write time.
         */
        StoreProviderConfigRequest: {
            provider_key: string;
            mode?: components["schemas"]["ModeEnum"];
            is_enabled?: boolean;
            public_metadata?: unknown;
            credentials?: string;
            webhook_secret?: string;
        };
        StoreSuspendRequestRequest: {
            /** @default  */
            reason: string;
        };
        StoreThemeConfig: {
            /** Format: uuid */
            readonly id: string;
            readonly theme_code: string;
            readonly theme_version_number: number;
            readonly settings: unknown;
            /** Format: date-time */
            readonly created_at: string;
            /** Format: date-time */
            readonly updated_at: string;
        };
        StorefrontCategory: {
            /** Format: uuid */
            readonly id: string;
            name: string;
            slug: string;
            /** Format: uuid */
            parent?: string | null;
            position?: number;
        };
        /**
         * @description Phase 13: everything the storefront renderer needs for one
         *     request -- who the store is (public fields only) and which
         *     theme/settings to render with. One call, not two, since every
         *     storefront page needs both.
         */
        StorefrontContext: {
            store: components["schemas"]["StorefrontStore"];
            theme: components["schemas"]["StoreThemeConfig"];
        };
        StorefrontProductDetail: {
            /** Format: uuid */
            readonly id: string;
            name: string;
            slug: string;
            description?: string;
            seo_title?: string;
            seo_description?: string;
            readonly options: components["schemas"]["ProductOption"][];
            readonly variants: components["schemas"]["StorefrontVariant"][];
        };
        /**
         * @description One row per product for grid/listing views. `price_amount`/
         *     `currency`/`compare_at_price_amount` come from the first active
         *     variant (by `position`) -- the view prefetches exactly that variant,
         *     ordered, so `.variants.all()[0]` never triggers a second query.
         */
        StorefrontProductList: {
            /** Format: uuid */
            readonly id: string;
            name: string;
            slug: string;
            readonly price_amount: number | null;
            readonly currency: string | null;
            readonly compare_at_price_amount: number | null;
        };
        /**
         * @description Phase 13 checkout's payment-method picker needs to know WHICH
         *     providers this store actually accepts -- never anything else
         *     (`credentials_hint`/`mode`/`public_metadata` are merchant-only).
         */
        StorefrontProvider: {
            provider_key: string;
        };
        /**
         * @description Plain `serializers.Serializer`, not bound to `apps.stores.models.Store`
         *     -- only the public-safe subset a shopper may see, assembled by the
         *     view from `request.tenant_store`. Never the full dashboard
         *     `StoreDetailSerializer` shape (that includes `contact_email`/
         *     `contact_phone`, merchant-only). `logo` IS public -- a shopper is
         *     supposed to see the store's own branding in the header/footer, same
         *     "public-safe" reasoning that already applies to `name`; real gap
         *     found live: every storefront theme's header/footer only ever had
         *     the store NAME to render (plain text wordmark), even for a store
         *     with a real logo uploaded -- same underlying serializer gap already
         *     fixed for the dashboard's own StoreListItemSerializer/
         *     StoreDetailSerializer (apps.stores.serializers).
         */
        StorefrontStore: {
            /** Format: uuid */
            id: string;
            name: string;
            default_currency: string;
            readonly logo: string | null;
        };
        StorefrontVariant: {
            /** Format: uuid */
            readonly id: string;
            sku: string;
            /** @description True only for the auto-created variant of a simple (option-less) product. */
            is_default?: boolean;
            position?: number;
            currency: string;
            price_amount: number;
            compare_at_price_amount?: number | null;
            weight_grams?: number | null;
            readonly option_values: components["schemas"]["StorefrontVariantOptionValue"][];
        };
        StorefrontVariantOptionValue: {
            readonly option_name: string;
            readonly value: string;
        };
        Subscription: {
            /** Format: uuid */
            readonly id: string;
            /** Format: uuid */
            readonly store_id: string;
            readonly status: components["schemas"]["Status3a5Enum"];
            readonly billing_interval: components["schemas"]["BillingIntervalEnum"];
            readonly plan_code: string;
            readonly plan_version_number: number;
            /** Format: date-time */
            readonly current_period_start: string;
            /** Format: date-time */
            readonly current_period_end: string;
            /** Format: date-time */
            readonly trial_ends_at: string | null;
            /** Format: date-time */
            readonly past_due_since: string | null;
            /** Format: date-time */
            readonly cancel_at: string | null;
            /** Format: date-time */
            readonly created_at: string;
        };
        /**
         * @description Phase D. `plan_version` is nested (not just an id) so the
         *     confirmation UI can show the actually-selected plan's real name/
         *     price without a second request. `theme_preset_id` stays a bare id
         *     (see models.py's docstring on why `apps.subscriptions` cannot
         *     resolve it to a name/preview itself) -- the frontend already has
         *     the full preset list from `GET /api/v1/themes/public/presets` and
         *     matches it locally.
         */
        SubscriptionCheckoutSession: {
            /** Format: uuid */
            readonly id: string;
            /** Format: uuid */
            readonly theme_preset_id: string | null;
            readonly plan_version: components["schemas"]["PublicPlanVersion"];
            readonly checkout_status: components["schemas"]["CheckoutStatusEnum"];
            readonly payment_status: components["schemas"]["PaymentStatusEnum"];
            readonly provisioning_status: components["schemas"]["ProvisioningStatusEnum"];
            /** Format: date-time */
            readonly created_at: string;
            /** Format: date-time */
            readonly updated_at: string;
        };
        /**
         * @description Phase E. Polled by the checkout page while `state` is
         *     pending/processing, and read once more for `failure_reason` on the
         *     failure screen.
         */
        SubscriptionPaymentIntent: {
            /** Format: uuid */
            readonly id: string;
            readonly amount: number;
            readonly currency: string;
            readonly state: components["schemas"]["StateEnum"];
            readonly failure_reason: string;
            /** Format: date-time */
            readonly created_at: string;
        };
        /**
         * @description Phase 12 (dashboard subscription-status UI). Read-only -- writes
         *     to Subscription remain `apps.subscriptions.services.upgrade_subscription`/
         *     `schedule_downgrade`, not exposed over HTTP yet (no reviewed
         *     self-service upgrade/downgrade UI architecture exists, approved
         *     Phase 10 technical debt, docs/PHASE_10_REPORT.md).
         */
        SubscriptionStatus: {
            /** Format: uuid */
            readonly id: string;
            readonly status: components["schemas"]["Status3a5Enum"];
            readonly billing_interval: components["schemas"]["BillingIntervalEnum"];
            /** Format: date-time */
            readonly current_period_start: string;
            /** Format: date-time */
            readonly current_period_end: string;
            /** Format: date-time */
            readonly trial_ends_at: string | null;
            /** Format: date-time */
            readonly cancel_at: string | null;
            readonly plan_code: string;
            readonly plan_name: string;
            readonly price_monthly: number;
            readonly price_yearly: number;
            readonly currency: string;
        };
        Supplier: {
            /** Format: uuid */
            readonly id: string;
            name: string;
            provider?: components["schemas"]["ProviderEnum"];
            is_active?: boolean;
            pricing_strategy?: components["schemas"]["PricingStrategyEnum"];
            pricing_value?: number;
            /** @description Minor units. Suggested price never yields less profit than this. */
            min_profit_amount?: number;
            /** Format: date-time */
            readonly last_synced_at: string | null;
            /** Format: date-time */
            readonly created_at: string;
        };
        SupplierProduct: {
            /** Format: uuid */
            readonly id: string;
            /** Format: uuid */
            readonly supplier: string;
            readonly external_id: string;
            readonly name: string;
            /** @description Minor units. */
            readonly cost_amount: number;
            readonly currency: string;
            readonly supplier_stock: number;
            readonly status: components["schemas"]["SupplierProductStatusEnum"];
            /** Format: uuid */
            readonly imported_variant: string | null;
            readonly suggested_price_amount: number;
        };
        /**
         * @description * `staged` - Staged
         *     * `imported` - Imported
         *     * `ignored` - Ignored
         * @enum {string}
         */
        SupplierProductStatusEnum: "staged" | "imported" | "ignored";
        SupplierRequest: {
            name: string;
            provider?: components["schemas"]["ProviderEnum"];
            is_active?: boolean;
            pricing_strategy?: components["schemas"]["PricingStrategyEnum"];
            pricing_value?: number;
            /** @description Minor units. Suggested price never yields less profit than this. */
            min_profit_amount?: number;
        };
        ThemePreset: {
            /** Format: uuid */
            readonly id: string;
            readonly name: string;
            readonly default_settings: unknown;
            /** Format: uri */
            readonly preview_image_url: string;
            readonly is_default: boolean;
            readonly theme_code: string;
            readonly theme_version_number: number;
        };
        VariantOptionValue: {
            readonly option_name: string;
            readonly value: string;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    api_v1_auth_email_verify_confirm_create: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description No response body */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    api_v1_auth_email_verify_resend_create: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description No response body */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    api_v1_auth_login_create: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PlatformTokenObtainPairRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["PlatformTokenObtainPairRequest"];
                "multipart/form-data": components["schemas"]["PlatformTokenObtainPairRequest"];
            };
        };
        responses: {
            /** @description No response body */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    api_v1_auth_logout_create: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description No response body */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    api_v1_auth_me_retrieve: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description No response body */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    api_v1_auth_mfa_enroll_confirm_create: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description No response body */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    api_v1_auth_mfa_enroll_start_create: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description No response body */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    api_v1_auth_mfa_verify_create: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description No response body */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    api_v1_auth_password_reset_create: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description No response body */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    api_v1_auth_password_reset_confirm_create: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description No response body */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    api_v1_auth_refresh_create: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PlatformTokenRefreshRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["PlatformTokenRefreshRequest"];
                "multipart/form-data": components["schemas"]["PlatformTokenRefreshRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PlatformTokenRefresh"];
                };
            };
        };
    };
    api_v1_auth_register_create: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description No response body */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    api_v1_dashboard_stores_list: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StoreListItem"][];
                };
            };
        };
    };
    api_v1_dashboard_stores_create: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CreateStoreRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["CreateStoreRequest"];
                "multipart/form-data": components["schemas"]["CreateStoreRequest"];
            };
        };
        responses: {
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StoreDetail"];
                };
            };
        };
    };
    api_v1_dashboard_stores_retrieve: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StoreDetail"];
                };
            };
        };
    };
    api_v1_dashboard_stores_partial_update: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["PatchedUpdateStoreRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["PatchedUpdateStoreRequest"];
                "multipart/form-data": components["schemas"]["PatchedUpdateStoreRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StoreDetail"];
                };
            };
        };
    };
    api_v1_dashboard_stores_analytics_overview_retrieve: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    api_v1_dashboard_stores_categories_retrieve: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description No response body */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    api_v1_dashboard_stores_categories_create: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description No response body */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    api_v1_dashboard_stores_inventory_adjust_create: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AdjustStockRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["AdjustStockRequest"];
                "multipart/form-data": components["schemas"]["AdjustStockRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StockBalance"];
                };
            };
        };
    };
    api_v1_dashboard_stores_inventory_balances_list: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StockBalance"][];
                };
            };
        };
    };
    api_v1_dashboard_stores_inventory_locations_list: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StockLocation"][];
                };
            };
        };
    };
    api_v1_dashboard_stores_inventory_locations_create: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StockLocationRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["StockLocationRequest"];
                "multipart/form-data": components["schemas"]["StockLocationRequest"];
            };
        };
        responses: {
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StockLocation"];
                };
            };
        };
    };
    api_v1_dashboard_stores_inventory_movements_retrieve: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description No response body */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    api_v1_dashboard_stores_orders_list: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OrderList"][];
                };
            };
        };
    };
    api_v1_dashboard_stores_orders_retrieve: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                order_id: string;
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Order"];
                };
            };
        };
    };
    api_v1_dashboard_stores_payment_intents_capture_cod_create: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                payment_intent_id: string;
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description No response body */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    api_v1_dashboard_stores_payments_providers_list: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StoreProviderConfig"][];
                };
            };
        };
    };
    api_v1_dashboard_stores_payments_providers_create: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StoreProviderConfigRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["StoreProviderConfigRequest"];
                "multipart/form-data": components["schemas"]["StoreProviderConfigRequest"];
            };
        };
        responses: {
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StoreProviderConfig"];
                };
            };
        };
    };
    api_v1_dashboard_stores_pricing_coupons_retrieve: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description No response body */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    api_v1_dashboard_stores_pricing_coupons_create: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description No response body */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    api_v1_dashboard_stores_pricing_tax_rates_retrieve: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description No response body */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    api_v1_dashboard_stores_pricing_tax_rates_create: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description No response body */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    api_v1_dashboard_stores_products_list: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Product"][];
                };
            };
        };
    };
    api_v1_dashboard_stores_products_create: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CreateProductRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["CreateProductRequest"];
                "multipart/form-data": components["schemas"]["CreateProductRequest"];
            };
        };
        responses: {
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Product"];
                };
            };
        };
    };
    api_v1_dashboard_stores_products_retrieve: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                product_id: string;
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Product"];
                };
            };
        };
    };
    api_v1_dashboard_stores_products_destroy: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                product_id: string;
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description No response body */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    api_v1_dashboard_stores_products_partial_update: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                product_id: string;
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["PatchedUpdateProductRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["PatchedUpdateProductRequest"];
                "multipart/form-data": components["schemas"]["PatchedUpdateProductRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Product"];
                };
            };
        };
    };
    api_v1_dashboard_stores_products_options_create: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                product_id: string;
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description No response body */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    api_v1_dashboard_stores_products_options_values_create: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                option_id: string;
                product_id: string;
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description No response body */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    api_v1_dashboard_stores_products_variants_create: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                product_id: string;
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description No response body */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    api_v1_dashboard_stores_products_variants_destroy: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                product_id: string;
                store_id: string;
                variant_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description No response body */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    api_v1_dashboard_stores_shipping_methods_rates_list: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                method_id: string;
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ShippingRate"][];
                };
            };
        };
    };
    api_v1_dashboard_stores_shipping_methods_rates_create: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                method_id: string;
                store_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ShippingRateRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["ShippingRateRequest"];
                "multipart/form-data": components["schemas"]["ShippingRateRequest"];
            };
        };
        responses: {
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ShippingRate"];
                };
            };
        };
    };
    api_v1_dashboard_stores_shipping_zones_list: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ShippingZone"][];
                };
            };
        };
    };
    api_v1_dashboard_stores_shipping_zones_create: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ShippingZoneRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["ShippingZoneRequest"];
                "multipart/form-data": components["schemas"]["ShippingZoneRequest"];
            };
        };
        responses: {
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ShippingZone"];
                };
            };
        };
    };
    api_v1_dashboard_stores_shipping_zones_methods_list: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                store_id: string;
                zone_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ShippingMethod"][];
                };
            };
        };
    };
    api_v1_dashboard_stores_shipping_zones_methods_create: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                store_id: string;
                zone_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ShippingMethodRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["ShippingMethodRequest"];
                "multipart/form-data": components["schemas"]["ShippingMethodRequest"];
            };
        };
        responses: {
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ShippingMethod"];
                };
            };
        };
    };
    api_v1_dashboard_stores_subscription_retrieve: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SubscriptionStatus"];
                };
            };
        };
    };
    api_v1_dashboard_stores_supplier_products_promote_create: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                store_id: string;
                supplier_product_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PromoteRequestRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["PromoteRequestRequest"];
                "multipart/form-data": components["schemas"]["PromoteRequestRequest"];
            };
        };
        responses: {
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    api_v1_dashboard_stores_suppliers_list: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Supplier"][];
                };
            };
        };
    };
    api_v1_dashboard_stores_suppliers_create: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SupplierRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["SupplierRequest"];
                "multipart/form-data": components["schemas"]["SupplierRequest"];
            };
        };
        responses: {
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Supplier"];
                };
            };
        };
    };
    api_v1_dashboard_stores_suppliers_products_list: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                store_id: string;
                supplier_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SupplierProduct"][];
                };
            };
        };
    };
    api_v1_dashboard_stores_suppliers_sync_create: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                store_id: string;
                supplier_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SupplierProduct"][];
                };
            };
        };
    };
    api_v1_dashboard_stores_tags_retrieve: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description No response body */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    api_v1_dashboard_stores_tags_create: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description No response body */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    api_v1_dashboard_stores_theme_retrieve: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StoreThemeConfig"];
                };
            };
        };
    };
    api_v1_dashboard_theme_presets_list: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ThemePreset"][];
                };
            };
        };
    };
    api_v1_platform_audit_logs_list: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AuditLog"][];
                };
            };
        };
    };
    api_v1_platform_overview_retrieve: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    api_v1_platform_plans_list: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Plan"][];
                };
            };
        };
    };
    api_v1_platform_plans_create: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PlanCreateRequestRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["PlanCreateRequestRequest"];
                "multipart/form-data": components["schemas"]["PlanCreateRequestRequest"];
            };
        };
        responses: {
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Plan"];
                };
            };
        };
    };
    api_v1_platform_plans_retrieve: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                plan_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PlanDetail"];
                };
            };
        };
    };
    api_v1_platform_plans_activate_create: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                plan_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Plan"];
                };
            };
        };
    };
    api_v1_platform_plans_deactivate_create: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                plan_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Plan"];
                };
            };
        };
    };
    api_v1_platform_plans_versions_create: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                plan_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PlanVersionPublishRequestRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["PlanVersionPublishRequestRequest"];
                "multipart/form-data": components["schemas"]["PlanVersionPublishRequestRequest"];
            };
        };
        responses: {
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PlanVersion"];
                };
            };
        };
    };
    api_v1_platform_stores_list: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PlatformStore"][];
                };
            };
        };
    };
    api_v1_platform_stores_retrieve: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PlatformStore"];
                };
            };
        };
    };
    api_v1_platform_stores_activate_create: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PlatformStore"];
                };
            };
        };
    };
    api_v1_platform_stores_suspend_create: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["StoreSuspendRequestRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["StoreSuspendRequestRequest"];
                "multipart/form-data": components["schemas"]["StoreSuspendRequestRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PlatformStore"];
                };
            };
        };
    };
    api_v1_platform_subscriptions_list: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Subscription"][];
                };
            };
        };
    };
    api_v1_platform_subscriptions_retrieve: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                subscription_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Subscription"];
                };
            };
        };
    };
    api_v1_platform_subscriptions_activate_create: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                subscription_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Subscription"];
                };
            };
        };
    };
    api_v1_platform_subscriptions_cancel_create: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                subscription_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Subscription"];
                };
            };
        };
    };
    api_v1_platform_users_list: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PlatformUser"][];
                };
            };
        };
    };
    api_v1_platform_users_retrieve: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PlatformUser"];
                };
            };
        };
    };
    api_v1_platform_users_mfa_reset_create: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description No response body */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    api_v1_storefront_cart_retrieve: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Cart"];
                };
            };
        };
    };
    api_v1_storefront_cart_coupon_create: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ApplyCouponRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["ApplyCouponRequest"];
                "multipart/form-data": components["schemas"]["ApplyCouponRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Cart"];
                };
            };
        };
    };
    api_v1_storefront_cart_coupon_destroy: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description No response body */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    api_v1_storefront_cart_items_create: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AddCartItemRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["AddCartItemRequest"];
                "multipart/form-data": components["schemas"]["AddCartItemRequest"];
            };
        };
        responses: {
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Cart"];
                };
            };
        };
    };
    api_v1_storefront_cart_items_destroy: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                item_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description No response body */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    api_v1_storefront_cart_items_partial_update: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                item_id: string;
            };
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["PatchedUpdateCartItemRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["PatchedUpdateCartItemRequest"];
                "multipart/form-data": components["schemas"]["PatchedUpdateCartItemRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Cart"];
                };
            };
        };
    };
    api_v1_storefront_cart_reprice_create: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Cart"];
                };
            };
        };
    };
    api_v1_storefront_cart_shipping_quotes_list: {
        parameters: {
            query: {
                country_code: string;
                postal_code?: string;
                region?: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ShippingQuote"][];
                };
            };
        };
    };
    api_v1_storefront_categories_list: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StorefrontCategory"][];
                };
            };
        };
    };
    api_v1_storefront_checkout_address_create: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CheckoutAddressRequestRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["CheckoutAddressRequestRequest"];
                "multipart/form-data": components["schemas"]["CheckoutAddressRequestRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CheckoutSession"];
                };
            };
        };
    };
    api_v1_storefront_checkout_complete_create: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Order"];
                };
            };
        };
    };
    api_v1_storefront_checkout_shipping_create: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CheckoutShippingRequestRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["CheckoutShippingRequestRequest"];
                "multipart/form-data": components["schemas"]["CheckoutShippingRequestRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CheckoutSession"];
                };
            };
        };
    };
    api_v1_storefront_checkout_start_create: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CheckoutSession"];
                };
            };
        };
    };
    api_v1_storefront_context_retrieve: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StorefrontContext"];
                };
            };
        };
    };
    api_v1_storefront_inventory_availability_retrieve: {
        parameters: {
            query?: {
                /** @description Repeatable -- one or more ProductVariant ids. */
                variant?: string[];
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    api_v1_storefront_payments_initiate_create: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PaymentInitiateRequestRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["PaymentInitiateRequestRequest"];
                "multipart/form-data": components["schemas"]["PaymentInitiateRequestRequest"];
            };
        };
        responses: {
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PaymentIntentResponse"];
                };
            };
        };
    };
    api_v1_storefront_payments_providers_list: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StorefrontProvider"][];
                };
            };
        };
    };
    api_v1_storefront_products_list: {
        parameters: {
            query?: {
                /** @description Filter by category slug. */
                category?: string;
                /** @description One of name (default), newest, price_asc, price_desc. */
                sort?: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StorefrontProductList"][];
                };
            };
        };
    };
    api_v1_storefront_products_retrieve: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                slug: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StorefrontProductDetail"];
                };
            };
        };
    };
    api_v1_subscriptions_billing_webhook_create: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description No response body */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    api_v1_subscriptions_checkout_sessions_current_retrieve: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SubscriptionCheckoutSession"];
                };
            };
        };
    };
    api_v1_subscriptions_checkout_sessions_current_create: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["StartSubscriptionCheckoutSessionRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["StartSubscriptionCheckoutSessionRequest"];
                "multipart/form-data": components["schemas"]["StartSubscriptionCheckoutSessionRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SubscriptionCheckoutSession"];
                };
            };
        };
    };
    api_v1_subscriptions_checkout_sessions_current_partial_update: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["PatchedSelectPlanRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["PatchedSelectPlanRequest"];
                "multipart/form-data": components["schemas"]["PatchedSelectPlanRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SubscriptionCheckoutSession"];
                };
            };
        };
    };
    api_v1_subscriptions_checkout_sessions_current_business_info_create: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["BusinessInfoRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["BusinessInfoRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CreatedStore"];
                };
            };
        };
    };
    api_v1_subscriptions_checkout_sessions_current_pay_create: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["InitiatePaymentRequest"];
                "application/x-www-form-urlencoded": components["schemas"]["InitiatePaymentRequest"];
                "multipart/form-data": components["schemas"]["InitiatePaymentRequest"];
            };
        };
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SubscriptionPaymentIntent"];
                };
            };
        };
    };
    api_v1_subscriptions_checkout_sessions_current_payment_intent_retrieve: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SubscriptionPaymentIntent"];
                };
            };
        };
    };
    api_v1_subscriptions_checkout_sessions_current_skip_payment_demo_create: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SubscriptionPaymentIntent"];
                };
            };
        };
    };
    api_v1_subscriptions_plans_public_list: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PublicPlanVersion"][];
                };
            };
        };
    };
    api_v1_themes_public_presets_list: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PublicThemePreset"][];
                };
            };
        };
    };
    api_v1_themes_public_presets_retrieve: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                preset_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PublicThemePreset"];
                };
            };
        };
    };
    api_v1_webhooks_payments_create: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                provider: string;
                store_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description No response body */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
}
