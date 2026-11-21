package ru.study.loadlab;

import java.util.List;
import java.util.Locale;
import java.util.NoSuchElementException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class TaskService {
    private final TaskRepository repository;
    public TaskService(TaskRepository repository) { this.repository = repository; }
    public List<Task> search(Task.Status status, int minPriority, String q, int limit, int offset) {
        return repository.search(status, minPriority, q.toLowerCase(Locale.ROOT), limit, offset);
    }
    public Task get(long id) {
        return repository.find(id).orElseThrow(() -> new NoSuchElementException("Task not found"));
    }
    @Transactional
    public Task create(String title, int priority) { return get(repository.insert(title.trim(), priority)); }
    @Transactional
    public Task update(long id, String title, int priority, Task.Status status) {
        if (repository.update(id, title.trim(), priority, status) == 0) throw new NoSuchElementException("Task not found");
        return get(id);
    }
    @Transactional
    public void delete(long id) {
        if (repository.delete(id) == 0) throw new NoSuchElementException("Task not found");
    }
}
