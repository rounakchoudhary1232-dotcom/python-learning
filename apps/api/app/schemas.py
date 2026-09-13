from pydantic import BaseModel, Field

class RegisterIn(BaseModel):
    email: str = Field(min_length=5, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=12, max_length=128)
    display_name: str = Field(min_length=1, max_length=120)
class LoginIn(BaseModel):
    email: str = Field(min_length=5, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str
class TextIn(BaseModel):
    content: str = Field(min_length=1, max_length=20000)
class CreateConversation(BaseModel):
    title: str = Field(default="New conversation", max_length=200)
class CreateMemory(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    kind: str = Field(default="fact", max_length=40)
class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=8000)
class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    project_id: int | None = None
    priority: str = Field(default="medium", pattern="^(low|medium|high)$")
    due_date: str | None = None
class MissionIn(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    objective: str = Field(min_length=1, max_length=8000)
class ApprovalDecision(BaseModel):
    approved: bool
class ToolCall(BaseModel):
    name: str = Field(pattern="^(time|calculator|workspace_info)$")
    expression: str | None = Field(default=None, max_length=100)
class SecurityTarget(BaseModel):
    target: str = Field(min_length=4, max_length=2048)
    authorized: bool

class UpgradeRequestIn(BaseModel):
    feature_request: str = Field(min_length=10, max_length=6000)

class UpgradeDecisionIn(BaseModel):
    approved: bool

class RollbackIn(BaseModel):
    confirmed: bool
