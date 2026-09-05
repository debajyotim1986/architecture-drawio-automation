# Decision Trees — External User Access to Looker on GKE (Hop-by-Hop Options)

Companion to the architecture document. Each hop of the flow has a decision tree showing **all viable connectivity/auth options**, with the recommended path marked. Option IDs (1A, 3B, 6D…) match the Excel decision matrix (`looker-external-access-decision-matrix.xlsx`) so both artifacts can be reviewed side-by-side with the central architect team.

Legend: ✅ Recommended · 🔁 Alternative · ⚠️ Conditional (needs a stated driver) · ❌ Not recommended

---

## Master Map — where each decision sits in the flow

```mermaid
flowchart TD
    U["External User Browser"] --> D1{"D1: Internet entry point?"}
    D1 --> H1["Hop 1: Edge - LB + Cloud Armor"]
    H1 --> D2{"D2: Where is the Login UI hosted / served?"}
    D2 --> H2["Hop 2: Apigee UI passthrough"]
    H2 --> D3{"D3: How are credentials authenticated?"}
    D3 --> H3["Hop 3: Auth broker to ID and Auth team"]
    H3 --> D4{"D4: How is the token delivered and stored?"}
    D4 --> H4["Hop 4: Token on client"]
    H4 --> D5{"D5: How is the JWT validated?"}
    D5 --> H5["Hop 5: Apigee data proxy"]
    H5 --> D6{"D6: Southbound trust and identity propagation?"}
    D6 --> H6["Hop 6: Apigee to GKE API"]
    H6 --> D7{"D7: How is Looker consumed?"}
    D7 --> H7["Hop 7: GKE API to Looker"]
    H7 --> D8{"D8: How does Looker isolate tenant data?"}
    D8 --> H8["Hop 8: Looker to DB"]
```

---

## D1 — Hop 1: User → Internet Entry Point

```mermaid
flowchart TD
    A{"How does external traffic enter?"} --> B["1A: Global External HTTPS LB + Cloud Armor + PSC NEG to Apigee"]
    A --> C["1B: Apigee default Google-managed hostname, no custom LB or WAF"]
    A --> D["1C: Regional External ALB + Cloud Armor"]
    A --> E["1D: Third-party CDN or WAF - Cloudflare / Akamai - in front of GCP LB"]
    A --> F["1E: L4 External LB - passthrough Network LB or TCP/SSL Proxy"]

    B --> B1["✅ SELECTED v1.3 - simplified: LB + PSC NEG exposure of the Apigee external gateway, WITHOUT Cloud Armor. Flag: Apigee SpikeArrest is now the only brute-force control on an internet-exposed login; Cloud Armor can be re-attached to the same LB later with zero redesign"]
    C --> C1["❌ Not recommended for prod: no custom domain or policy control"]
    D --> D1x["⚠️ Conditional: choose only for strict data-residency / regional-only mandate"]
    E --> E1["❌ Deselected v1.3: Akamai removed from the chain per decision"]
    F --> F1["❌ Not viable: Apigee X external exposure requires the L7 Application LB + PSC NEG; L4 also loses HTTP routing, L7 WAF rules and managed certs"]
```

**Key question for the architect team:** decided — direct Apigee external gateway exposure (no Akamai, no Cloud Armor). Remaining check: agree the abuse-control budget on `/auth/login` (SpikeArrest per-IP limits, CAPTCHA threshold), since Apigee is now the only line of defense; revisit Cloud Armor if login abuse is observed.

---

## D2 — Hop 2: Edge → Login UI Hosting & Delivery

```mermaid
flowchart TD
    A{"Where do the login SPA assets live?"} --> B["2A: GCS bucket + Cloud CDN behind Apigee passthrough"]
    A --> C["2B: NGINX pod in GKE behind Apigee passthrough"]
    A --> D["2C: Firebase Hosting behind Apigee"]
    A --> E["2D: HTML returned from Apigee AssignMessage policy"]

    B --> B1["✅ Recommended: cheapest, zero pods to run, CDN caching, versioned rollout by bucket path"]
    C --> C1["🔁 Alternative: keeps everything in GKE; pick if team wants one deploy pipeline for UI + API"]
    D --> D1x["⚠️ Conditional: nice DX, but adds a product outside the core stack"]
    E --> E1["❌ Not recommended: unmaintainable, no caching, policy bloat"]
```

**Key question:** does the platform team prefer one GKE pipeline for everything (2B), or minimal-ops static hosting (2A)?

---

## D3 — Hop 3: Credential Authentication (the biggest decision)

```mermaid
flowchart TD
    A{"How does the user authenticate?"} --> B["3A: Apigee-brokered POST of userid+passkey to ID and Auth REST service - current pattern"]
    A --> C["3B: OIDC Authorization Code + PKCE - browser redirects to IdP-hosted login"]
    A --> D["3C: SAML 2.0 federation"]
    A --> E["3D: WebAuthn / FIDO2 passkeys - challenge-response, passwordless"]
    A --> F["3E: GCP Identity Platform - CIAM - fronting the ID and Auth service"]

    B --> B1["✅ Recommended as-is fit: internal proxy never internet-exposed - browser can only reach the external proxy; ID and A API validates userid/password against OSIS DB; Apigee adds SpikeArrest, threat protection, CAPTCHA"]
    B1 --> B2{"Does ID and Auth team also support OIDC?"}
    B2 -- "Yes, roadmap allows" --> C
    B2 -- "No, REST contract only" --> B3["Stay on 3A; harden with 3b pre-checks + 4D refresh rotation"]

    C --> C1["🔁 Strongest standard: credentials never transit your stack; MFA/social login for free; needs IdP UI support"]
    D --> D1x["⚠️ Conditional: only if partner enterprises mandate SAML; heavier, XML-based"]
    E --> E1["⚠️ Conditional: best phishing resistance; changes Hop 3 to challenge relay - flag if passkey means FIDO2 not password"]
    F --> F1["🔁 Alternative: managed CIAM - lockout, MFA, brute-force protection out of the box - if ID team agrees to sit behind it"]
```

**Key questions:** (1) Is "passkey" a password or a FIDO2 passkey? (2) Can the ID & Auth team expose OIDC, or is the REST+JWT JSON contract fixed?

---

## D4 — Hop 4: Token Delivery & Client-Side Storage

```mermaid
flowchart TD
    A{"How does the JWT reach and live on the client?"} --> B["4A: HttpOnly Secure SameSite cookie set by Apigee"]
    A --> C["4B: JWT in JSON body, held in memory, sent as Bearer header"]
    A --> D["4C: JWT in localStorage"]
    A --> E["4D: Short-lived access token + rotating refresh token"]

    B --> B1["✅ Recommended: immune to XSS token theft; browser auto-attaches; needs CSRF protection - SameSite covers most"]
    C --> C1["🔁 Alternative: needed if API consumers are non-browser clients too; lost on tab refresh"]
    D --> D1x["❌ Not recommended: readable by any XSS payload"]
    E --> E1["✅ Recommended add-on to 4A or 4B: 15-60 min access TTL, refresh via /auth/refresh brokered by Apigee"]
```

---

## D5 — Hop 5: JWT Validation at the Gateway

```mermaid
flowchart TD
    A{"How is the token validated on /api/**?"} --> B["5A: Apigee VerifyJWT against ID team JWKS URI"]
    A --> C["5B: Static public key stored in Apigee KVM"]
    A --> D["5C: Opaque token + introspection ServiceCallout to ID team"]
    A --> E["5D: No gateway check - validate only inside the GKE API"]
    A --> F["5E: Double validation - Apigee VerifyJWT + re-validate in GKE API"]
    A --> G["5F: jti deny-list in Apigee cache for revocation"]

    B --> B1["✅ Recommended baseline: signature, exp, iss, aud, custom claims; automatic key rotation via JWKS"]
    C --> C1["❌ Not recommended: manual rotation, outage risk on key change"]
    D --> D1x["⚠️ Conditional: pick if instant revocation is mandatory; adds latency + dependency per call"]
    E --> E1["❌ Not recommended: unauthenticated traffic reaches the VPC; loses edge analytics"]
    F --> F1["✅ Recommended add-on: defense-in-depth; document that Apigee is the authoritative check"]
    G --> G1["✅ Recommended add-on: logout + compromise handling without full introspection cost"]
```

**Key question:** what is the revocation SLA? If "seconds", 5C introspection wins; if "token TTL is acceptable", 5A + 5F wins.

---

## D6 — Hop 6: Southbound Trust (Apigee → GKE) & Identity Propagation

```mermaid
flowchart TD
    A{"Network path Apigee to GKE?"} --> B["6A: PSC service attachment + mTLS to GKE ingress"]
    A --> C["6B: Internal HTTPS LB over shared or peered VPC, one-way TLS + firewall rules"]
    A --> D["6C: Public GKE endpoint with IP allow-list"]

    B --> B1["✅ Recommended: no VPC peering sprawl, private, producer-consumer model, strongest transport trust"]
    C --> C1["🔁 Alternative: fine where shared VPC already exists; weaker than mTLS unless added"]
    D --> D1x["❌ Not recommended: public surface + spoofable trust"]

    B1 --> E{"How does user identity reach the API?"}
    C1 --> E
    E --> F["6D: Apigee strips client headers, injects trusted X-User-Id / X-Tenant-Id / X-Roles"]
    E --> G["6E: Forward the original JWT; API re-validates against same JWKS"]
    E --> H["6F: Token exchange - Apigee mints a new internal gateway-signed token"]

    F --> F1["✅ Recommended: simple, fast; safe ONLY because transport guarantees the sender is Apigee"]
    G --> G1["✅ Recommended add-on: pairs with 5E defense-in-depth"]
    H --> H1["⚠️ Conditional: cleanest zero-trust story; adds a signing service to build and operate"]
```

---

## D7 — Hop 7: GKE API → Looker Consumption Model

```mermaid
flowchart TD
    A{"How do external users consume Looker?"} --> B["7A: Signed SSO Embed URL - iframe dashboards"]
    A --> C["7B: Looker REST API - run_query / render - behind a custom UI"]
    A --> D["7C: Private embed without SSO"]
    A --> E["7D: Full reverse-proxy of the Looker UI to external users"]

    B --> B1["✅ Recommended for dashboards: per-user embed identity, user attributes drive RLS, least custom code"]
    C --> C1["🔁 Alternative: full UI control, no Looker chrome; you rebuild filters, drill-downs, exports"]
    D --> D1x["❌ Not recommended: no per-user identity, no row-level security"]
    E --> E1["❌ Not recommended: session and cookie complexity, exposes native Looker surface"]

    B1 --> F{"Reverse proxy tech in front of Looker pods?"}
    C1 --> F
    F --> G["7E: NGINX - simple, well-known"]
    F --> H["7F: Envoy / Istio mesh sidecars"]
    G --> G1["✅ Recommended if no mesh today"]
    H --> H1["⚠️ Conditional: pick only if the cluster already runs a mesh - gets mTLS + policy for free"]
```

**Key question:** do users need the Looker look-and-feel (7A) or a fully branded custom experience (7B)? This drives months of effort difference.

---

## D8 — Hop 8: Looker → Database Tenant Isolation

```mermaid
flowchart TD
    A{"How is tenant data isolated at query time?"} --> B["8A: Single service credential + Looker user-attribute access filters - RLS"]
    A --> C["8B: Per-tenant DB connections or schemas mapped in Looker"]
    A --> D["8C: BigQuery authorized views per tenant"]

    B --> B1["✅ Recommended: standard multi-tenant embed pattern; isolation enforced in the model layer"]
    C --> C1["⚠️ Conditional: hard isolation for regulated tenants; connection sprawl, ops overhead"]
    D --> D1x["⚠️ Conditional: strong fit when the warehouse is BigQuery; view maintenance per tenant"]
```

---

## Recommended Golden Path (one line)

**1A-lite (LB + PSC exposure, no Cloud Armor — flagged) → 2A → 3A via internal-proxy chain to ID&A API + OSIS DB (evolve to 3B) → 4A + 4D → 5A + 5E + 5F → 6A + 6D + 6E → 7A + 7E → 8A**

Every ✅ above composes into this path; every ⚠️ has a named driver the architect team must confirm before selecting it. D1 is decided (direct Apigee exposure, edge WAF removed — SpikeArrest is the only abuse control, flagged); D3's transport is decided (proxy chain to the internal proxy, credentials validated against OSIS).
