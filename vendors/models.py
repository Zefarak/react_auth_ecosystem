from django.db import models
from django.db.models import Sum
from django.conf import settings
from django.shortcuts import reverse
from django.db.models.signals import post_delete
from django.dispatch import receiver

from tinymce.models import HTMLField
from decimal import Decimal



from frontend.tools import initial_date

# Create your models here.


CURRENCY = settings.CURRENCY
TAXES_CHOICES = (
    ('a', 0),
    ('b', 13),
    ('c', 24)
)

PAYMENT_METHOD_CATEGORY = (
    ('a', 'Αντικαταβολή'),
    ('b', 'Τραπεζική ΚατάΘεση')
)


class PaymentMethod(models.Model):
    title = models.CharField(max_length=200, unique=True, verbose_name='Ονομασια')
    category = models.CharField(max_length=1, choices=PAYMENT_METHOD_CATEGORY, verbose_name='Κατηγορια')

    def __str__(self):
        return self.title

    @staticmethod
    def filters_data(request, qs):

        return qs

    def get_edit_url(self):
        return reverse('payment_method_update', kwargs={'pk': self.id})

    def get_delete_url(self):
        return reverse('payment_method_delete', kwargs={'pk': self.pk})


class Vendor(models.Model):
    active = models.BooleanField(default=True, verbose_name='Ενεργό')
    title = models.CharField(max_length=200, unique=True, verbose_name='Εταιρία')
    owner = models.CharField(max_length=200, blank=True, verbose_name='Ιδιοκτήτης')
    afm = models.CharField(max_length=150, blank=True, verbose_name='ΑΦΜ')
    doy = models.CharField(max_length=150, blank=True, verbose_name='ΔΟΥ')
    phone = models.CharField(max_length=200, blank=True, verbose_name='Σταθερο Τηλεφωνο')
    cellphone = models.CharField(max_length=200, blank=True, verbose_name='Κινητό')
    email = models.EmailField(blank=True)
    site = models.URLField(blank=True, null=True)
    description = models.TextField(blank=True, null=True, verbose_name='Λεπτομεριες')
    address = models.CharField(max_length=240, blank=True, null=True, verbose_name='Διευθυνση')
    city = models.CharField(max_length=240, blank=True, null=True, verbose_name='Πολη')
    balance = models.DecimalField(decimal_places=2, max_digits=50, default=0.00, verbose_name='Υπόλοιπο')
    paid_value = models.DecimalField(decimal_places=2, max_digits=50, default=0.00)
    value = models.DecimalField(decimal_places=2, max_digits=50, default=0.00)
    taxes_modifier = models.CharField(max_length=1, choices=TAXES_CHOICES, default='c')

    class Meta:
        ordering = ['title']

    def __str__(self):
        return f'{self.title}'

    def save(self, *args, **kwargs):
        self.balance = self.value - self.paid_value
        self.title = self.title.upper()
        super().save(*args, **kwargs)

    def update_paid_value(self):
        qs = self.payments.all()
        value = qs.aggregate(Sum('value'))['value__sum'] if qs.exists() else 0
        self.paid_value = Decimal(value)
        self.save()

    def update_value(self):
        qs = self.invoices.all()
        value = qs.aggregate(Sum('final_value'))['final_value__sum'] if qs.exists() else 0
        self.value = Decimal(value)
        self.save()

    def tag_balance(self):
        return f'{self.balance} {CURRENCY}'

    tag_balance.short_description = 'Υπολοίπο'


class Employer(models.Model):
    active = models.BooleanField(default=True)
    title = models.CharField(max_length=200, verbose_name='Ονομασια')
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='persons', verbose_name='Προμηθευτης')
    phone = models.CharField(max_length=10, blank=True, verbose_name='Τηλεφωνο')
    cellphone = models.CharField(max_length=10, blank=True, verbose_name='Κινητο')
    email = models.EmailField(blank=True)

    class Meta:
        ordering = ['title', ]

    def __str__(self):
        return self.title


class VendorBankingAccount(models.Model):
    payment_method = models.ForeignKey(PaymentMethod, on_delete=models.CASCADE, related_name='banking_accounts', null=True, verbose_name='Τροπος Πληρωμής')
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, verbose_name='Προμηθευτής', related_name='bankings')
    name = models.CharField(max_length=150, blank=True, verbose_name='Ονομα Δικαιούχου')
    iban = models.CharField(max_length=150, blank=True, )
    code = models.CharField(max_length=200, blank=True, verbose_name='Αριθμός Λογαριασμού')

    def __str__(self):
        return f'{self.vendor.title} {self.payment_method.title}'

    def tag_vendor(self):
        return f'{self.vendor.title}'


class Invoice(models.Model):
    date = models.DateField()
    title = models.CharField(max_length=150)
    payment_method = models.ForeignKey(PaymentMethod, on_delete=models.PROTECT, null=True,)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='invoices')
    value = models.DecimalField(decimal_places=2, max_digits=20)
    extra_value = models.DecimalField(decimal_places=2, max_digits=20)
    final_value = models.DecimalField(decimal_places=2, max_digits=20)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['-date']

    def save(self, *args, **kwargs):
        self.final_value = self.value + self.extra_value
        print('here')
        super(Invoice, self).save(*args, **kwargs)
        if self.vendor:
            self.vendor.update_value()

    def __str__(self):
        return f'{self.title}'

    def tag_value(self):
        return f'{self.final_value} {CURRENCY}'

    def tag_payment_method(self):
        return f'{self.payment_method.title}'

    def tag_vendor(self):
        return f'{self.vendor.title}'

    @staticmethod
    def filters_data(request, qs):
        date_start, date_end, date_range = initial_date(request, 6)
        print('start', date_start, 'end', date_end)
        search_name = request.GET.get('search_name', None)
        qs = qs.filter(title__icontains=search_name) if search_name else qs
        if date_start and date_end:
            print('hitted!', date_end, date_start)
            qs = qs.filter(date__range=[date_start, date_end])
        print(qs.count())
        return qs


class Payment(models.Model):
    date = models.DateField(verbose_name='Ημερομηνία')
    title = models.CharField(max_length=150, verbose_name='Τίτλος')
    payment_method = models.ForeignKey(PaymentMethod, on_delete=models.PROTECT, null=True,
                                       verbose_name='Τροπος Πληρωμής')
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='payments', verbose_name='Προμηθευτής')
    value = models.DecimalField(decimal_places=2, max_digits=20, verbose_name='Αξία')
    description = models.TextField(blank=True, verbose_name='Περιγραφή')

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f'{self.title}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.vendor:
            self.vendor.update_paid_value()

    def tag_payment_method(self):
        return f'{self.payment_method.title}'

    def tag_value(self):
        return f'{self.value} {CURRENCY}'

    def filters_data(request, qs):
        date_start, date_end, date_range = initial_date(request, 6)
        if date_start and date_end:
            qs = qs.filter(date__range=[date_start, date_end])
        return qs

    # for reports

    @property
    def report_date(self):
        return self.date

    def report_expense_type(self):
        return f'Πληρωμη-{self.vendor}'

    def report_value(self):
        return self.value


class Note(models.Model):
    status = models.BooleanField(default=True, verbose_name='Κατάσταση')
    vendor_related = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='notes')
    date = models.DateTimeField(auto_now_add=True)
    title = models.CharField(max_length=200, blank=True, null=True)
    text = HTMLField(blank=True)

    def __str__(self):
        return f'{self.title}' if self.title else 'Σημειωση'


@receiver(post_delete, sender=Payment)
def update_vendor_on_delete(sender, instance, **kwargs):
    instance.vendor.update_paid_value()


@receiver(post_delete, sender=Invoice)
def update_vendor_invoice_on_delete(sender, instance, **kwargs):
    instance.vendor.update_value()
