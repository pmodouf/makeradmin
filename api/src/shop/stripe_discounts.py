from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
import time
from typing import TYPE_CHECKING, Dict, List, Optional
from venv import logger
import stripe
from membership.models import DiscountCoupon
from service.config import debug_mode
from service.error import InternalServerError

# from api.src.service import db
from shop.stripe_util import retry
from basic_types.enums import PriceLevel
from service.db import db_session

from shop.stripe_constants import MakerspaceMetadataKeys

if TYPE_CHECKING:
    from membership.models import Member
    from shop.models import Product


@dataclass
class Discount:
    coupon: Optional[stripe.Coupon]
    fraction_off: Decimal


DISCOUNT_FRACTIONS: Optional[Dict[PriceLevel, Discount]] = {
    price_level: None for price_level in PriceLevel
}


def get_price_level_for_member(member: "Member") -> PriceLevel:
    return PriceLevel(member.price_level)


def get_discount_for_product(product: "Product", price_level: PriceLevel) -> Discount:
    """
    Check if this product gets a discount at the given price level, or if it stays at the normal price
    """
    if price_level in map(
        PriceLevel,
        product.get_metadata(MakerspaceMetadataKeys.ALLOWED_PRICE_LEVELS, []),
    ):
        return get_discount_fraction_off(price_level)
    else:
        return get_discount_fraction_off(PriceLevel.Normal)


def get_discount_fraction_off(price_level: PriceLevel) -> Discount:
    if DISCOUNT_FRACTIONS[price_level] is None:
        DISCOUNT_FRACTIONS[price_level] = _query_discount_fraction_off(price_level)
    return DISCOUNT_FRACTIONS[price_level]


def _query_discount_fraction_off(price_level: PriceLevel) -> Discount:
    if price_level == PriceLevel.Normal:
        return Discount(None, Decimal(0))

    coupons: List[stripe.Coupon] = retry(lambda: stripe.Coupon.list())
    coupons = [
        coupon
        for coupon in coupons
        if coupon["metadata"].get(MakerspaceMetadataKeys.PRICE_LEVEL.value, None)
        == price_level.value
    ]
    if len(coupons) == 0:
        raise Exception(
            f"Could not find stripe coupon for {MakerspaceMetadataKeys.PRICE_LEVEL.value}={price_level.value}"
        )
    if len(coupons) > 1:
        raise Exception(
            f"Found multiple stripe coupons for {MakerspaceMetadataKeys.PRICE_LEVEL.value}={price_level.value}"
        )

    coupon = coupons[0]
    if (coupon["amount_off"] or 0) > 0:
        raise Exception(
            f"Stripe coupon {coupon.stripe_id} has a fixed amount off. Only a percentage off is supported by MakerAdmin"
        )

    percent_off = coupon["percent_off"]
    assert isinstance(percent_off, float) and percent_off >= 0 and percent_off <= 100
    return Discount(coupon, Decimal(percent_off) / 100)


def get_stripe_coupon(makeradmin_discount: DiscountCoupon) -> stripe.Coupon | None:
    try:
        return retry(
            lambda: stripe.Coupon.retrieve(id=makeradmin_discount.stripe_discount_id)
        )
    except stripe.InvalidRequestError as e:
        logger.warning(
            f"failed to retrive product from stripe for makeradmin product with id {makeradmin_discount}, {e}"
        )
        return None


def get_stripe_coupon_id(makeradmin_discount: DiscountCoupon) -> str:
    prefix = "debug" if debug_mode() else "prod"
    return f"{prefix}_{makeradmin_discount.id}"


def create_stripe_coupon(makeradmin_discount: DiscountCoupon) -> stripe.Coupon:
    stripe_discount = retry(
        lambda: stripe.Coupon.create(
            duration="forever",
            percent_off=makeradmin_discount.discount_percentage,
            metadata={"makeradmin_id": makeradmin_discount.id},
        )
    )
    makeradmin_discount.stripe_discount_id = stripe_discount.id
    db_session.flush()
    return stripe_discount


def delete_stripe_coupon(makeradmin_discount: DiscountCoupon) -> stripe.Coupon:
    stripe_discount = retry(
        lambda: stripe.Coupon.delete(makeradmin_discount.stripe_discount_id)
    )
    makeradmin_discount.stripe_discount_id = None
    db_session.flush()
    return stripe_discount


def find_or_create_stripe_coupon(
    makeradmin_discount: DiscountCoupon,
) -> stripe.Discount:
    stripe_discount = get_stripe_coupon(makeradmin_discount)
    if stripe_discount is None:
        stripe_discount = create_stripe_coupon(makeradmin_discount)
    return stripe_discount


def deactivate_stripe_coupon(stripe_coupon: stripe.Coupon) -> stripe.Coupon:
    return retry(lambda: stripe.Coupon.delete(stripe_coupon.id, active=True))


"""
def activate_stripe_coupon(stripe_coupon: stripe.Coupon) -> stripe.Coupon:
    return retry(lambda: stripe.Coupon.modify(stripe_coupon.id, active=True))

"""


def replace_stripe_coupon(
    makeradmin_discount: DiscountCoupon,
    stripe_coupon: stripe.Coupon,
) -> stripe.Coupon:
    if get_stripe_coupon_id(makeradmin_discount) != stripe_coupon.id:
        raise InternalServerError(
            f"The coupon for stripe with id {stripe_coupon.id} does not match with the coupon {makeradmin_discount.id} in makeradmin."
        )

    deactivate_stripe_coupon(stripe_coupon)
    stripe_coupon = get_stripe_coupon(makeradmin_discount)
    if stripe_coupon is None:
        raise RuntimeError(
            f"Failed to fetch stripe coupon for makeradmin {makeradmin_discount.id}"
        )
    new_stripe_coupon = create_stripe_coupon(stripe_coupon)
    new_makeradmin_discount = create_stripe_coupon(makeradmin_discount)
    if new_stripe_coupon != new_makeradmin_discount:
        raise RuntimeError(
            f"The stripe coupon does not match makeradmin coupon{stripe_coupon.id}"
        )
    if new_stripe_coupon is None:
        raise RuntimeError(f"Failed to replace stripe coupon {stripe_coupon.id}")

    return new_stripe_coupon
