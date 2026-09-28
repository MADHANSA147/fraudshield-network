from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, frozen=True)


class Plan(StrictModel):
    name: str = Field(default="Consortium fraud detector", min_length=3, max_length=100)
    mode: Literal["public_fixture", "public_paysim", "confidential"] = "public_fixture"
    epsilon_cap: float = Field(default=8.0, gt=0, le=8)
    evaluation_epsilon: float = Field(default=0.5, gt=0, le=2)
    delta: float = Field(default=1e-6, gt=0, lt=1e-3)
    rounds: int = Field(default=3, ge=1, le=20)
    local_steps: int = Field(default=12, ge=1, le=200)
    capacity: int = Field(default=2048, ge=128, le=1048576)
    batch_size: int = Field(default=128, ge=8, le=4096)
    clipping_norm: float = Field(default=1.0, gt=0, le=10)
    learning_rate: float = Field(default=0.1, gt=0, le=1)
    positive_weight: float = Field(default=5.0, ge=1, le=100)
    seed: int = Field(default=42, ge=0, le=2**31 - 1)
    max_fpr: float = Field(default=0.01, gt=0, lt=0.2)
    min_recall: float = Field(default=0.6, gt=0, le=1)
    noninferiority_margin: float = Field(default=0.05, ge=0, le=0.1)
    participants: tuple[str, str, str] = ("atlas", "meridian", "harbor")

    @model_validator(mode="after")
    def valid_plan(self):
        if self.evaluation_epsilon >= self.epsilon_cap:
            raise ValueError("Evaluation budget must leave room for training")
        if self.batch_size > self.capacity or self.capacity % self.batch_size:
            raise ValueError("Capacity must be divisible by batch size")
        if len(set(self.participants)) != 3 or set(self.participants) != {"atlas", "meridian", "harbor"}:
            raise ValueError("This deployment requires the three enrolled institutions")
        return self

    @property
    def sample_rate(self):
        return self.batch_size / self.capacity


class Transaction(StrictModel):
    amount: float = Field(ge=0, le=1e12)
    type: str = Field(max_length=30)
    step: int = Field(ge=0)
    oldbalanceOrg: float | None = Field(default=None, ge=0, le=1e12)


class ReleasePolicy(StrictModel):
    version: str = "1"
    max_fpr: float = 0.01
    min_recall: float = 0.6
    noninferiority_margin: float = 0.05


INSTITUTIONS = {
    "atlas": {"name": "Atlas Payments", "region": "Digital payments", "color": "#58c7b0"},
    "meridian": {"name": "Meridian Financial", "region": "Retail banking", "color": "#8b9cf7"},
    "harbor": {"name": "Harbor Credit", "region": "Member finance", "color": "#e6b96a"},
}
