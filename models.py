from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LeadState:
    lead_id: str
    first_name: str
    last_name: str
    company_name: str
    niche: str
    website_url: Optional[str] = None
    location: Optional[str] = None
    tier: Optional[str] = None
    est_revenue_level: Optional[str] = None

    primary_website_weakness: Optional[str] = None
    leverage_angle_used: Optional[str] = None
    personalized_note: Optional[str] = None
    confidence_before_sending: Optional[float] = None

    outreach_channel: Optional[str] = None
    subject_line_used: Optional[str] = None
    pitch_version: Optional[str] = None
    email_body: Optional[str] = None

    response_status: Optional[str] = None
    call_booked: Optional[bool] = None

    deal_stage: Optional[str] = None
    proposed_price_usd: Optional[float] = None

    @classmethod
    def from_dict(cls, data: dict) -> "LeadState":
        return cls(
            lead_id=data["lead_id"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            company_name=data["company_name"],
            niche=data["niche"],
            website_url=data.get("website_url"),
            location=data.get("location"),
            tier=data.get("tier"),
            est_revenue_level=data.get("est_revenue_level"),
            primary_website_weakness=data.get("primary_website_weakness"),
            leverage_angle_used=data.get("leverage_angle_used"),
            personalized_note=data.get("personalized_note"),
            confidence_before_sending=data.get("confidence_before_sending"),
            outreach_channel=data.get("outreach_channel"),
            subject_line_used=data.get("subject_line_used"),
            pitch_version=data.get("pitch_version"),
            email_body=data.get("email_body"),
            response_status=data.get("response_status"),
            call_booked=data.get("call_booked"),
            deal_stage=data.get("deal_stage"),
            proposed_price_usd=data.get("proposed_price_usd"),
        )

    def to_dict(self) -> dict:
        return {
            "lead_id": self.lead_id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "company_name": self.company_name,
            "niche": self.niche,
            "website_url": self.website_url,
            "location": self.location,
            "tier": self.tier,
            "est_revenue_level": self.est_revenue_level,
            "primary_website_weakness": self.primary_website_weakness,
            "leverage_angle_used": self.leverage_angle_used,
            "personalized_note": self.personalized_note,
            "confidence_before_sending": self.confidence_before_sending,
            "outreach_channel": self.outreach_channel,
            "subject_line_used": self.subject_line_used,
            "pitch_version": self.pitch_version,
            "email_body": self.email_body,
            "response_status": self.response_status,
            "call_booked": self.call_booked,
            "deal_stage": self.deal_stage,
            "proposed_price_usd": self.proposed_price_usd,
        }
