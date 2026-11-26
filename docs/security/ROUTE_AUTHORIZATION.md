# Route authorization

Protected routes should use `login_required` and `permission_required`. Resource resolvers must load resource ownership/team/department attributes from the database using the route resource identifier; never construct trusted scope context from client-supplied ownership fields.

Permission checks are required for reads, writes, downloads, previews, exports, background jobs, bulk actions and administrative operations. Deny by default. The decorator is a convenience layer and does not replace service-level checks or transaction safeguards.
