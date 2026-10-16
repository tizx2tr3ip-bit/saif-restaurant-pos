# Saif Cafe Customer Ordering
LGPL-3. Odoo Community20 addon depending on pos_self_order.

Public customer page: /cafe/<config_id>. Enabled explicitly per config. Supports car and opaque table QR links, simple products, notes, server totals and native draft POS orders. No live payments.

See CUSTOMER-UI-DELIVERY-AR.md at project root for installation, tests, limits, QR links and rollback. Tests in tests/ are explicitly invoked standalone/shell scripts, not auto-imported Odoo test suites. Do not run seed or smoke scripts on production.
