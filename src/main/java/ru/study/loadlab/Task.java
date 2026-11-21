package ru.study.loadlab;

/** A flat CRUD value shared by the service, JDBC mapping and response serialization. */
public record Task(long id, String title, int priority, Status status) {
    public enum Status { OPEN, DONE }
}
