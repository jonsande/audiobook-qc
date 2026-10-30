CREATE TABLE incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT CHECK (id>0),
                created_at TEXT NOT NULL CHECK (
                    length(created_at)=32 AND substr(created_at,27)='+00:00'
                    AND julianday(created_at) IS NOT NULL),
                updated_at TEXT NOT NULL CHECK (
                    length(updated_at)=32 AND substr(updated_at,27)='+00:00'
                    AND julianday(updated_at) IS NOT NULL),
                incident_type TEXT NOT NULL CHECK (incident_type IN ('TEXT', 'PRON', 'DICC', 'RUID', 'RESP', 'INTER', 'OTRO')),
                audio_filename TEXT NOT NULL CHECK (
                    typeof(audio_filename)='text' AND audio_filename <> ''),
                audio_path TEXT NOT NULL CHECK (
                    typeof(audio_path)='text' AND audio_path <> ''),
                audio_position_seconds REAL NOT NULL CHECK (
                    typeof(audio_position_seconds) IN ('real','integer') AND
                    audio_position_seconds BETWEEN -1.7976931348623157e308
                    AND 1.7976931348623157e308),
                document TEXT NOT NULL CHECK (
                    typeof(document)='text' AND document <> ''),
                page INTEGER NOT NULL CHECK (typeof(page)='integer' AND page>=0),
                selected_text TEXT NOT NULL CHECK (
                    typeof(selected_text)='text' AND selected_text <> ''),
                generic_description TEXT CHECK (
                    generic_description IS NULL OR typeof(generic_description)='text'),
                custom_comment TEXT CHECK (
                    custom_comment IS NULL OR typeof(custom_comment)='text'),
                exported INTEGER NOT NULL DEFAULT 0 CHECK (
                    typeof(exported)='integer' AND exported IN (0,1))
            );
PRAGMA user_version=1;
