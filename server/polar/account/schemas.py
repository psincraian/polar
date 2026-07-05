from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BeforeValidator, Field, model_validator

from polar.enums import AccountType
from polar.kit.address import Address, AddressInput
from polar.kit.schemas import Schema
from polar.models.account import Account as AccountModel
from polar.models.account import PayoutSchedule
from polar.organization.schemas import Organization
from polar.user.schemas import UserBase


class StripeAccountCountry(StrEnum):
    AL = "AL"
    AG = "AG"
    AR = "AR"
    AM = "AM"
    AU = "AU"
    AT = "AT"
    BH = "BH"
    BE = "BE"
    BO = "BO"
    BA = "BA"
    BG = "BG"
    KH = "KH"
    CA = "CA"
    CL = "CL"
    CO = "CO"
    CR = "CR"
    HR = "HR"
    CY = "CY"
    CZ = "CZ"
    CI = "CI"
    DK = "DK"
    DO = "DO"
    EC = "EC"
    EG = "EG"
    SV = "SV"
    EE = "EE"
    ET = "ET"
    FI = "FI"
    FR = "FR"
    GM = "GM"
    DE = "DE"
    GH = "GH"
    GR = "GR"
    GT = "GT"
    GY = "GY"
    HK = "HK"
    HU = "HU"
    IS = "IS"
    IN = "IN"
    ID = "ID"
    IE = "IE"
    IL = "IL"
    IT = "IT"
    JM = "JM"
    JP = "JP"
    JO = "JO"
    KE = "KE"
    KW = "KW"
    LV = "LV"
    LI = "LI"
    LT = "LT"
    LU = "LU"
    MO = "MO"
    MG = "MG"
    MY = "MY"
    MT = "MT"
    MU = "MU"
    MX = "MX"
    MD = "MD"
    MN = "MN"
    MA = "MA"
    NA = "NA"
    NL = "NL"
    NZ = "NZ"
    NG = "NG"
    MK = "MK"
    NO = "NO"
    OM = "OM"
    PA = "PA"
    PY = "PY"
    PE = "PE"
    PH = "PH"
    PL = "PL"
    PT = "PT"
    QA = "QA"
    RO = "RO"
    RW = "RW"
    SA = "SA"
    SN = "SN"
    RS = "RS"
    SG = "SG"
    SK = "SK"
    SI = "SI"
    ZA = "ZA"
    KR = "KR"
    ES = "ES"
    LK = "LK"
    LC = "LC"
    SE = "SE"
    CH = "CH"
    TZ = "TZ"
    TH = "TH"
    TT = "TT"
    TN = "TN"
    TR = "TR"
    AE = "AE"
    GB = "GB"
    US = "US"
    UY = "UY"
    UZ = "UZ"
    VN = "VN"
    DZ = "DZ"
    AO = "AO"
    AZ = "AZ"
    BS = "BS"
    BD = "BD"
    BJ = "BJ"
    BT = "BT"
    BW = "BW"
    BN = "BN"
    GA = "GA"
    KZ = "KZ"
    LA = "LA"
    MC = "MC"
    MZ = "MZ"
    NE = "NE"
    PK = "PK"
    SM = "SM"
    TW = "TW"


class AccountCreateForOrganization(Schema):
    organization_id: UUID = Field(
        description="Organization ID to create or get account for"
    )

    account_type: Literal[AccountType.stripe]
    country: Annotated[StripeAccountCountry, BeforeValidator(str.upper)]


PayoutScheduleWeekday = Annotated[
    int,
    Field(
        ge=0,
        le=6,
        description=(
            "Day of the week a weekly payout is created on, "
            "where 0 is Monday and 6 is Sunday."
        ),
    ),
]

PayoutScheduleDayOfMonth = Annotated[
    int,
    Field(
        ge=1,
        le=31,
        description=(
            "Day of the month a monthly payout is created on (1-31). "
            "If the month is shorter, the payout happens on its last day, "
            "so 31 always means the last day of the month."
        ),
    ),
]


class Account(Schema):
    id: UUID
    account_type: AccountType
    status: AccountModel.Status
    stripe_id: str | None
    is_details_submitted: bool
    is_charges_enabled: bool
    is_payouts_enabled: bool
    country: str
    credit_balance: int

    billing_name: str | None
    billing_address: Address | None
    billing_additional_info: str | None
    billing_notes: str | None

    payout_schedule: PayoutSchedule
    payout_schedule_weekday: int | None
    payout_schedule_day_of_month: int | None

    users: list[UserBase]
    organizations: list[Organization]


class AccountUpdate(Schema):
    billing_name: str | None = Field(
        default=None,
        description="Billing name that should appear on the reverse invoice.",
    )
    billing_address: AddressInput | None = Field(
        default=None,
        description="Billing address that should appear on the reverse invoice.",
    )
    billing_additional_info: str | None = Field(
        default=None,
        description="Additional information that should appear on the reverse invoice.",
    )
    billing_notes: str | None = Field(
        default=None,
        description="Notes that should appear on the reverse invoice.",
    )
    payout_schedule: PayoutSchedule | None = Field(
        default=None,
        description=(
            "How payouts should be triggered for this account. "
            "When set to `weekly`, `payout_schedule_weekday` is required. "
            "When set to `monthly`, `payout_schedule_day_of_month` is required."
        ),
    )
    payout_schedule_weekday: PayoutScheduleWeekday | None = None
    payout_schedule_day_of_month: PayoutScheduleDayOfMonth | None = None

    @model_validator(mode="after")
    def validate_payout_schedule(self) -> Self:
        if self.payout_schedule == PayoutSchedule.weekly:
            if self.payout_schedule_weekday is None:
                raise ValueError(
                    "payout_schedule_weekday is required for a weekly payout schedule."
                )
        elif self.payout_schedule == PayoutSchedule.monthly:
            if self.payout_schedule_day_of_month is None:
                raise ValueError(
                    "payout_schedule_day_of_month is required "
                    "for a monthly payout schedule."
                )
        return self


class AccountLink(Schema):
    url: str
