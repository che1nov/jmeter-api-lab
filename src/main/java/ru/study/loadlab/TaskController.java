package ru.study.loadlab;

import java.net.URI;
import java.util.List;
import java.util.NoSuchElementException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ProblemDetail;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/tasks")
public class TaskController {
    private final TaskService service;
    public TaskController(TaskService service) { this.service = service; }
    public record CreateTask(String title, Integer priority) { }
    public record UpdateTask(String title, Integer priority, Task.Status status) { }
    public record TaskPage(List<Task> items, int limit, int offset) { }

    @GetMapping
    TaskPage search(@RequestParam(required = false) Task.Status status,
                    @RequestParam(defaultValue = "1") int minPriority,
                    @RequestParam(defaultValue = "") String q,
                    @RequestParam(defaultValue = "10") int limit,
                    @RequestParam(defaultValue = "0") int offset) {
        if (minPriority < 1 || minPriority > 5 || limit < 1 || limit > 100 || offset < 0 || q.length() > 120)
            throw new IllegalArgumentException("Invalid search parameters");
        return new TaskPage(service.search(status, minPriority, q, limit, offset), limit, offset);
    }
    @GetMapping("/{id}") Task get(@PathVariable long id) { return service.get(id); }
    @PostMapping
    ResponseEntity<Task> create(@RequestBody CreateTask input) {
        validate(input.title(), input.priority());
        Task task = service.create(input.title(), input.priority());
        return ResponseEntity.created(URI.create("/api/tasks/" + task.id())).body(task);
    }
    @PutMapping("/{id}")
    Task update(@PathVariable long id, @RequestBody UpdateTask input) {
        validate(input.title(), input.priority());
        if (input.status() == null) throw new IllegalArgumentException("status is required");
        return service.update(id, input.title(), input.priority(), input.status());
    }
    @DeleteMapping("/{id}")
    ResponseEntity<Void> delete(@PathVariable long id) { service.delete(id); return ResponseEntity.noContent().build(); }

    private void validate(String title, Integer priority) {
        if (title == null || title.isBlank() || title.length() > 120 || priority == null || priority < 1 || priority > 5)
            throw new IllegalArgumentException("title: 1..120 characters; priority: 1..5");
    }
    @ExceptionHandler(IllegalArgumentException.class)
    ProblemDetail invalid(IllegalArgumentException ex) {
        return ProblemDetail.forStatusAndDetail(HttpStatus.BAD_REQUEST, ex.getMessage());
    }
    @ExceptionHandler(NoSuchElementException.class)
    ProblemDetail missing(NoSuchElementException ex) {
        return ProblemDetail.forStatusAndDetail(HttpStatus.NOT_FOUND, ex.getMessage());
    }
}
