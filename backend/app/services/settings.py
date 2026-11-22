from sqlalchemy.orm import Session

from app.models import SiteSetting


def registration_enabled(db: Session) -> bool:
    setting = db.get(SiteSetting, "registration_enabled")
    if setting is None:
        return True
    return setting.setting_value.strip().lower() in {"1", "true", "yes", "on"}


def set_registration_enabled(db: Session, enabled: bool) -> None:
    setting = db.get(SiteSetting, "registration_enabled")
    value = "true" if enabled else "false"
    if setting is None:
        db.add(
            SiteSetting(
                setting_key="registration_enabled",
                setting_value=value,
            )
        )
    else:
        setting.setting_value = value
