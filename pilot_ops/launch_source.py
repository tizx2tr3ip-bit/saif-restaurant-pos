"""Use only the downloaded Odoo namespace; image supplies third-party dependencies."""
import odoo

odoo.__path__ = ['/opt/odoo-source/odoo']
import odoo.cli

if __name__ == '__main__':
    odoo.cli.main()
