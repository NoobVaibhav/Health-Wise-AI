from pydantic import BaseModel


class EmployeeOut(BaseModel):
    id: int
    full_name: str
    email: str
    designation: str | None
    phone: str | None
    is_active: bool
