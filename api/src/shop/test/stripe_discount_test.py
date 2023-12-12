from datetime import datetime, timezone
from decimal import Decimal
from unittest import skipIf
from venv import logger
from shop import stripe_discounts
from service.config import debug_mode
from shop.stripe_discounts import (
    Discount,
    create_stripe_coupon,
    get_stripe_coupon,
    find_or_create_stripe_coupon,
)
from shop.test.subscriptions_test import FakeCardPmToken, attach_and_set_payment_method
from membership.member_auth import hash_password
from test_aid.obj import DEFAULT_PASSWORD
from test_aid.systest_base import VALID_3DS_CARD_NO
from test_aid.test_base import FlaskTestBase, ShopTestMixin
from test_aid.db import DbFactory
from service.db import db_session
import stripe
import membership.models
import shop.models
import messages.models
from shop import stripe_util
from typing import List, cast
from membership.models import DiscountCoupon, Member
import core.models
from shop import stripe_constants


class StripeDiscountTest(ShopTestMixin, FlaskTestBase):
    # The products id in makeradmin have to be unique in each test to prevent race conditions
    # Some of the tests here will generate new objects in stripe. They are all ran in test mode
    # You can clear the test area in stripe's developer dashboard.

    models = [membership.models, messages.models, shop.models, core.models]
    self_stripe_id = 2

    @skipIf(not stripe.api_key, "stripe util tests require stripe api key in .env file")
    def setUp(self) -> None:
        super().setUp()
        self.seen_discounts: List[DiscountCoupon] = []

    def tearDown(self) -> None:
        # It is not possible to delete prices through the api so we set them as inactive instead
        for makeradmin_discount in self.seen_discounts:
            stripe_discounts.delete_stripe_coupon(makeradmin_discount)
        return super().tearDown()

    def create_member_that_can_pay(
        self, card_token: FakeCardPmToken, signed_labaccess: bool = True
    ) -> Member:
        member = self.db.create_member(password=hash_password(DEFAULT_PASSWORD))
        self.set_payment_method(member, card_token)
        if signed_labaccess:
            member.labaccess_agreement_at = datetime.now()
        return member

    def set_payment_method(self, member: Member, card_token: FakeCardPmToken) -> None:
        attach_and_set_payment_method(member, card_token)

    def test_create_discounts(self):
        discount_data = self.db.create_discount()
        self.seen_discounts.append(discount_data)
        stripe_test_discount = stripe_discounts.find_or_create_stripe_coupon(
            discount_data
        )
        self.assertEqual(
            stripe_test_discount.percent_off, discount_data.discount_percentage
        )
        self.assertEqual(stripe_test_discount.id, discount_data.stripe_discount_id)
        query_discount = (
            db_session.query(DiscountCoupon)
            .filter(DiscountCoupon.id == discount_data.id)
            .one_or_none()
        )
        self.assertEqual(query_discount.id, discount_data.id)
        self.assertEqual(query_discount.stripe_discount_id, stripe_test_discount.id)

    def test_replace_coupon(self):
        makeradmin_coupon = self.db.create_discount()
        self.seen_discounts.append(makeradmin_coupon)
        stripe_coupon = stripe_discounts.find_or_create_stripe_coupon(makeradmin_coupon)
        assert stripe_coupon
        makeradmin_coupon.discount_percentage = 10
        db_session.commit()

        new_stripe_discount = stripe_discounts.replace_stripe_coupon(
            makeradmin_coupon, stripe_coupon
        )
        self.assertEqual(
            new_stripe_discount.percent_off, makeradmin_coupon.discount_percentage
        )
        self.assertEqual(new_stripe_discount.id, makeradmin_coupon.stripe_discount_id)
