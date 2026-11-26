"""Software release planning and controlled lifecycle operations."""
from __future__ import annotations
from itoms.db.connection import get_connection
from itoms.services.authorization import ResourceContext,has_permission
class ReleaseError(ValueError): pass
RELEASE_STATES={"PLANNED","IN_TEST","READY","APPROVED","DEPLOYING","RELEASED","ROLLED_BACK","CANCELLED"}
RELEASE_TRANSITIONS={"PLANNED":{"IN_TEST","CANCELLED"},"IN_TEST":{"READY","CANCELLED"},"READY":{"APPROVED","CANCELLED"},"APPROVED":{"DEPLOYING","CANCELLED"},"DEPLOYING":{"RELEASED","ROLLED_BACK"},"RELEASED":set(),"ROLLED_BACK":set(),"CANCELLED":set()}
def _ctx(row): return ResourceContext(owner_employee_id=row["created_by"],resource_type="release",resource_id=str(row["release_id"]))
def list_releases(*,actor_employee_id:int):
    conn=get_connection(); cur=conn.cursor(dictionary=True)
    try: cur.execute("SELECT r.release_id,r.release_key,r.version_label,r.status,r.target_at,r.released_at,r.created_by,s.service_name FROM software_releases r LEFT JOIN service_records s ON s.service_id=r.service_id ORDER BY r.created_at DESC LIMIT 200"); rows=cur.fetchall()
    finally: cur.close(); conn.close()
    return [dict(x,can_update=has_permission(actor_employee_id,"release.update",_ctx(x))) for x in rows if has_permission(actor_employee_id,"release.read",_ctx(x))]
def create_release(*,actor_employee_id:int,release_key:str,version_label:str,release_notes:str,service_id:int|None,target_at:str|None,change_id:int|None):
    if not has_permission(actor_employee_id,"release.create"): raise ReleaseError("Not authorized to create releases.")
    release_key=release_key.strip().upper(); version_label=version_label.strip()
    if not release_key or len(release_key)>100 or not version_label or len(version_label)>80: raise ReleaseError("Release key and version are required and must fit their limits.")
    conn=get_connection(); cur=conn.cursor()
    try:
        if service_id is not None:
            cur.execute("SELECT service_id,owner_team_id FROM service_records WHERE service_id=%s",(service_id,)); service=cur.fetchone()
            if not service: raise ReleaseError("Service record not found.")
            if not has_permission(actor_employee_id,"service.inventory.read",ResourceContext(team_id=service[1],resource_type="service",resource_id=str(service[0]))): raise ReleaseError("Not authorized to link this service.")
        if change_id is not None:
            cur.execute("SELECT change_id,requested_by FROM change_records WHERE change_id=%s",(change_id,)); change=cur.fetchone()
            if not change: raise ReleaseError("Change record not found.")
            if not has_permission(actor_employee_id,"change.read",ResourceContext(owner_employee_id=change[1],resource_type="change",resource_id=str(change[0]))): raise ReleaseError("Not authorized to link this change.")
        cur.execute("INSERT INTO software_releases (release_key,service_id,version_label,release_notes,target_at,created_by) VALUES (%s,%s,%s,%s,%s,%s)",(release_key,service_id,version_label,release_notes.strip(),target_at or None,actor_employee_id))
        release_id=int(cur.lastrowid)
        if change_id is not None: cur.execute("INSERT INTO release_change_links (release_id,change_id) VALUES (%s,%s)",(release_id,change_id))
        cur.execute("INSERT INTO audit_events (actor_employee_id,event_key,target_type,target_id,outcome) VALUES (%s,'RELEASE_CREATED','release',%s,'SUCCESS')",(actor_employee_id,str(release_id)))
        conn.commit(); return release_id
    except Exception: conn.rollback(); raise
    finally: cur.close(); conn.close()
def transition_release(*,actor_employee_id:int,release_id:int,new_status:str):
    if new_status not in RELEASE_STATES: raise ReleaseError("Invalid release status.")
    conn=get_connection(); cur=conn.cursor(dictionary=True)
    try: cur.execute("SELECT release_id,created_by,status FROM software_releases WHERE release_id=%s",(release_id,)); row=cur.fetchone()
    finally: cur.close(); conn.close()
    if not row or not has_permission(actor_employee_id,"release.update",_ctx(row)): raise ReleaseError("Release record not found or not authorized.")
    if new_status not in RELEASE_TRANSITIONS.get(row["status"],set()): raise ReleaseError("This release transition is not allowed.")
    conn=get_connection(); cur=conn.cursor()
    try:
        cur.execute("SELECT status,created_by FROM software_releases WHERE release_id=%s FOR UPDATE",(release_id,)); current=cur.fetchone()
        if not current or current[0]!=row["status"] or current[1]!=row["created_by"]: raise ReleaseError("Release changed; reload and try again.")
        cur.execute("UPDATE software_releases SET status=%s,released_at=CASE WHEN %s='RELEASED' THEN UTC_TIMESTAMP() ELSE released_at END WHERE release_id=%s",(new_status,new_status,release_id))
        cur.execute("INSERT INTO audit_events (actor_employee_id,event_key,target_type,target_id,outcome) VALUES (%s,'RELEASE_STATUS_CHANGED','release',%s,'SUCCESS')",(actor_employee_id,str(release_id)))
        conn.commit()
    except Exception: conn.rollback(); raise
    finally: cur.close(); conn.close()