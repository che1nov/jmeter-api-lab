package ru.study.loadlab;

import java.sql.Statement;
import java.util.List;
import java.util.Optional;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.jdbc.support.GeneratedKeyHolder;
import org.springframework.stereotype.Repository;

@Repository
public class TaskRepository {
    private final JdbcTemplate jdbc;
    private static final RowMapper<Task> ROW = (rs, n) -> new Task(rs.getLong("id"), rs.getString("title"),
            rs.getInt("priority"), Task.Status.valueOf(rs.getString("status")));
    public TaskRepository(JdbcTemplate jdbc) { this.jdbc = jdbc; }

    public List<Task> search(Task.Status status, int minPriority, String q, int limit, int offset) {
        return jdbc.query("SELECT * FROM tasks WHERE (? IS NULL OR status=?) AND priority>=? "
                        + "AND LOCATE(?, LOWER(title))>0 ORDER BY id LIMIT ? OFFSET ?",
                ROW, status == null ? null : status.name(), status == null ? null : status.name(),
                minPriority, q, limit, offset);
    }
    public Optional<Task> find(long id) {
        return jdbc.query("SELECT * FROM tasks WHERE id=?", ROW, id).stream().findFirst();
    }
    public long insert(String title, int priority) {
        var key = new GeneratedKeyHolder();
        jdbc.update(connection -> {
            var statement = connection.prepareStatement("INSERT INTO tasks(title,priority,status) VALUES(?,?,'OPEN')",
                    Statement.RETURN_GENERATED_KEYS);
            statement.setString(1, title);
            statement.setInt(2, priority);
            return statement;
        }, key);
        return key.getKey().longValue();
    }
    public int update(long id, String title, int priority, Task.Status status) {
        return jdbc.update("UPDATE tasks SET title=?,priority=?,status=? WHERE id=?", title, priority, status.name(), id);
    }
    public int delete(long id) { return jdbc.update("DELETE FROM tasks WHERE id=?", id); }
}
