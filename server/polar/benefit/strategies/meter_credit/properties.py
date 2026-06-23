from ..base.properties import BenefitGrantProperties, BenefitProperties


class BenefitMeterCreditProperties(BenefitProperties, total=False):
    meter_id: str
    units: int
    rollover: bool
    per_seat: bool


class BenefitGrantMeterCreditProperties(BenefitGrantProperties, total=False):
    last_credited_meter_id: str
    last_credited_units: int
    last_credited_at: str
