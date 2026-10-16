# نظام سيف للمطاعم — مساحة العمل المشتركة

مستودع التعاون لتطوير نظام نقاط البيع للمطعم على Odoo Community 20.

يتضمن فرع التسليم إضافات الطلب الحالية وحزمة تشغيل محلية معزولة. لا توجد قواعد بيانات أو أسرار أو Enterprise. ندمج إلى main بعد مراجعة إبراهيم.

## تنظيم العمل

- `custom_addons/`: إضافات المشروع، تُنقل لاحقاً من النسخة المعتمدة لدى سيف.
- `pilot_ops/`: إعداد التشغيل المحلي والنسخ الاحتياطي لاحقاً — إبراهيم.
- `pilot_tests/`: اختبارات القبول والتكامل لاحقاً — إبراهيم.
- `docs/pilot/`: توثيق التجربة والتشغيل — إبراهيم.
- `docs/coordination.md`: طريقة التعاون وتقسيم العمل.

## طريقة المشاركة

1. استنسخ المستودع في GitHub Desktop.
2. اضغط Fetch origin ثم Pull قبل بدء العمل.
3. أنشئ فرعاً لكل مهمة، مثل `saif/customer-order` أو `ibrahim/pilot-setup`.
4. سجّل التغييرات في Commit ثم Publish branch وافتح Pull Request إلى `main`.
5. يراجع الزميل التغييرات قبل الدمج؛ لا تعملوا على الملف نفسه بالتزامن دون اتفاق.

لا ترفع كلمات المرور أو `.env` أو بيانات العملاء أو قواعد البيانات أو ملفات النسخ الاحتياطي. احتفظ بكل بيئة تشغيل وقاعدة بيانات محلية مستقلة.

## نسخة Odoo المرجعية

المستهدف بحسب تسليم المشروع: Odoo Community 20 عند commit:
`3ab21d47f92a25fd973e0687886a9d3ea5946ed4`

جُلب هذا المصدر الرسمي وتحققنا من commit في نسخة التسليم المستقلة. يشير إليه Git submodule وsource.lock.json؛ لا يُنسخ مصدر أودو إلى تاريخ مشروعنا. لا توجد إضافات Enterprise.


## ابدأ هنا — حزمة المصدر والتجربة

[خطوات Windows والتشغيل](docs/pilot/START-HERE-AR.md) · [حالة الميزات والاختبارات](docs/pilot/STATUS-AR.md) · [مهمة إبراهيم التالية](docs/pilot/IBRAHIM-NEXT-TASK.md) · [تقسيم المهام](docs/coordination.md).

المصدر الرسمي مثبت كـGit submodule تحت `vendor/odoo` ويطابق `source.lock.json`. لتقليل التنزيل، استنسخ مستودع الفريق أولاً ثم استخدم أمر `source` أدناه لجلب commit واحد. لا تنسخ تثبيت Windows الحالي فوق هذا المصدر.

```sh
python pilot_ops/team.py init --name ibrahim --port 8072
python pilot_ops/team.py source
python pilot_ops/team.py bootstrap
```

في Windows يمكن استخدام `py -3` بدلاً من `python`. يحتاج Git وPython 3.9+ وDocker Desktop مع Linux containers. هذه حزمة تطوير محلية فقط؛ لا تنشرها للإنتاج.
