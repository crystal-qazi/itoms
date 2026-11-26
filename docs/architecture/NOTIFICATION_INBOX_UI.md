# In-app Notification Inbox

The authenticated `/notifications/` route displays only the current employee's inbox. The employee identity comes from the validated server-side session, never from a request parameter. Users may filter to unread notifications and mark only their own items as read.

Notification creation remains a service-layer operation requiring the explicit `notifications.send` permission. The notification and in-app outbox row are written in one transaction, with an audit event. The migration registers the sender permission but does not grant it to any role.

The inbox does not yet provide email delivery, push delivery, bulk actions, retention controls or notification preference management. Outbox worker execution and recovery remain operational follow-up work.