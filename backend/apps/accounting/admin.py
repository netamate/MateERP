from django.contrib import admin

from .models import Account, ExchangeRate, FiscalPeriod, JournalEntry, JournalLine, TaxCode

admin.site.register(Account)
admin.site.register(FiscalPeriod)
admin.site.register(TaxCode)
admin.site.register(ExchangeRate)
admin.site.register(JournalEntry)
admin.site.register(JournalLine)
