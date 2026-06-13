from pydantic import BaseModel


class MonitorOffer(BaseModel):
    sdp: str
    type: str  # "offer"


class MonitorAnswer(BaseModel):
    sdp: str
    type: str  # "answer"
