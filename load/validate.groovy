import groovy.json.JsonSlurper

// Use vars.get(), not JMeter ${...} substitutions, so compiled scripts remain safe to cache.
try {
    String label = prev.getSampleLabel()
    String expected = label.startsWith('02') ? '201' : label.startsWith('06') ? '204' : '200'
    assert prev.getResponseCode() == expected : 'HTTP ' + prev.getResponseCode() + ', expected ' + expected
    if (label.startsWith('06')) {
        assert prev.getResponseData().length == 0 : 'DELETE must have an empty body'
    } else {
        def data = new JsonSlurper().parseText(prev.getResponseDataAsString())
        if (label.startsWith('01')) {
            assert data.items instanceof List
            assert data.limit == vars.get('limit').toInteger()
            assert data.offset == vars.get('offset').toInteger()
            assert data.items.size() <= data.limit
            long last = -1
            data.items.each { task ->
                assert task.id instanceof Number && task.id > last
                assert task.title instanceof String && task.title.toLowerCase().contains(vars.get('category'))
                assert task.priority >= vars.get('minPriority').toInteger() && task.priority <= 5
                assert task.status == vars.get('filterStatus')
                last = task.id
            }
        } else {
            assert data.id instanceof Number && data.id > 0
            if (label.startsWith('02')) vars.put('taskId', data.id.toString())
            assert data.id.toString() == vars.get('taskId')
            boolean updated = label.startsWith('04') || label.startsWith('05')
            assert data.title == vars.get(updated ? 'updatedTitle' : 'title')
            assert data.priority == vars.get(updated ? 'updatedPriority' : 'priority').toInteger()
            assert data.status == (updated ? 'DONE' : 'OPEN')
        }
    }
} catch (Throwable problem) {
    AssertionResult.setFailure(true)
    AssertionResult.setFailureMessage(problem.toString())
}
