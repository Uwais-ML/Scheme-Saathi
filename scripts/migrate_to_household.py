"""Migration script: Converts existing single-user profiles to Household models."""

import json
import shutil
from pathlib import Path
from config.settings import settings
from state.models import Household, Member, UserProfile
from state.store import get_connection, init_db, save_household


def migrate_to_household(db_path: Path | str | None = None) -> int:
    """Migrate single profiles into household records. Returns migrated count."""
    path = Path(db_path) if db_path else settings.SQLITE_DB_PATH
    if not path.exists():
        print(f"Database {path} does not exist. Initializing fresh DB.")
        init_db(path)
        return 0

    # Step 1: Create a safe backup first
    backup_path = path.with_suffix(".db.bak")
    shutil.copy2(path, backup_path)
    print(f"Backed up database to: {backup_path}")

    init_db(path)

    migrated_count = 0
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, profile_json FROM user_profiles")
        rows = cursor.fetchall()

        cursor.execute("SELECT household_id FROM households")
        existing_hh_ids = {r[0] for r in cursor.fetchall()}

        for user_id, profile_json in rows:
            hh_id = user_id
            if hh_id in existing_hh_ids:
                print(f"Already migrated: {hh_id}")
                continue

            try:
                prof_data = json.loads(profile_json)
                profile = UserProfile.model_validate(prof_data)
                self_member = Member(
                    member_id=f"{user_id}_self",
                    display_name=profile.name or "Self",
                    relation="self",
                    profile=profile,
                    documents=profile.documents,
                    schemes_eligible=profile.schemes_eligible,
                    form_drafts={profile.active_scheme: profile.form_draft} if profile.active_scheme and profile.form_draft else {},
                )
                household = Household(
                    household_id=hh_id,
                    members=[self_member],
                    active_member_id=self_member.member_id,
                )
                save_household(household, db_path=path)
                migrated_count += 1
                print(f"Migrated: {user_id} → household_{hh_id}")
            except Exception as e:
                print(f"Error migrating {user_id}: {e}")

    print(f"\nMigration complete. Total new households created: {migrated_count}")
    return migrated_count


if __name__ == "__main__":
    migrate_to_household()
