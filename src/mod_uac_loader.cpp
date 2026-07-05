// modules/mod-uac/src/mod_uac_loader.cpp
//
// mod-uac ships only data (SQL + client patch) and has no gameplay scripts.
// This no-op loader exists solely so AzerothCore registers the module: the
// presence of src/ is what places mod-uac into AC_MODULES_LIST, which is what
// makes the DB updater apply data/sql/db-world/*.sql.
// Name convention: "Add" + <folder name, '-' -> '_'> + "Scripts".
void Addmod_uacScripts()
{
}
