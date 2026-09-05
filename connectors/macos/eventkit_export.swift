import EventKit
import Foundation

// This program deliberately writes only its JSON result to stdout.  The Python
// wrapper keeps that result in the ignored runtime directory; diagnostics never
// contain event or reminder text.

struct SourceResult: Encodable {
    let ok: Bool
    let error: String?
    let items: [[String: AnyCodable]]
}

// A small type eraser keeps the emitted JSON explicit without pulling a JSON
// dependency into the command-line helper.
enum AnyCodable: Encodable {
    case string(String)
    case integer(Int64)
    case bool(Bool)
    case null

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .string(let value): try container.encode(value)
        case .integer(let value): try container.encode(value)
        case .bool(let value): try container.encode(value)
        case .null: try container.encodeNil()
        }
    }
}

struct Payload: Encodable {
    let calendar: SourceResult
    let reminders: SourceResult
}

func epoch(_ date: Date) -> Int64 { Int64(date.timeIntervalSince1970) }

func describe(_ error: Error?) -> String {
    guard let error = error else { return "access was not granted" }
    return (error as NSError).localizedDescription
}

func requestEvents(_ store: EKEventStore) -> (Bool, String?) {
    if #available(macOS 14.0, *) {
        let semaphore = DispatchSemaphore(value: 0)
        var granted = false
        var failure: Error?
        store.requestFullAccessToEvents { ok, error in
            granted = ok
            failure = error
            semaphore.signal()
        }
        semaphore.wait()
        return (granted, granted ? nil : describe(failure))
    }
    let status = EKEventStore.authorizationStatus(for: .event)
    return (status == .authorized, status == .authorized ? nil : "Calendar access is not authorized")
}

func requestReminders(_ store: EKEventStore) -> (Bool, String?) {
    if #available(macOS 14.0, *) {
        let semaphore = DispatchSemaphore(value: 0)
        var granted = false
        var failure: Error?
        store.requestFullAccessToReminders { ok, error in
            granted = ok
            failure = error
            semaphore.signal()
        }
        semaphore.wait()
        return (granted, granted ? nil : describe(failure))
    }
    let status = EKEventStore.authorizationStatus(for: .reminder)
    return (status == .authorized, status == .authorized ? nil : "Reminders access is not authorized")
}

let arguments = CommandLine.arguments
guard let startIndex = arguments.firstIndex(of: "--range-start"),
      let endIndex = arguments.firstIndex(of: "--range-end"),
      startIndex + 1 < arguments.count, endIndex + 1 < arguments.count,
      let startSeconds = TimeInterval(arguments[startIndex + 1]),
      let endSeconds = TimeInterval(arguments[endIndex + 1]) else {
    fputs("usage: eventkit_export --range-start EPOCH --range-end EPOCH\\n", stderr)
    exit(2)
}

let store = EKEventStore()
let rangeStart = Date(timeIntervalSince1970: startSeconds)
let rangeEnd = Date(timeIntervalSince1970: endSeconds)

let calendarAccess = requestEvents(store)
var calendarItems: [[String: AnyCodable]] = []
if calendarAccess.0 {
    let predicate = store.predicateForEvents(withStart: rangeStart, end: rangeEnd, calendars: nil)
    for event in store.events(matching: predicate) {
        // EventKit expands repeating events for the predicate.  The occurrence
        // start is part of the ID because calendarItemIdentifier names the series.
        let instanceID = "\(event.calendarItemIdentifier):\(epoch(event.startDate))"
        calendarItems.append([
            "id": .string(instanceID),
            "title": .string(event.title ?? ""),
            "start": .integer(epoch(event.startDate)),
            "end": .integer(epoch(event.endDate)),
            "all_day": .bool(event.isAllDay),
            "calendar": .string(event.calendar.title),
            "location": .string(event.location ?? "")
        ])
    }
}

let reminderAccess = requestReminders(store)
var reminderItems: [[String: AnyCodable]] = []
if reminderAccess.0 {
    let predicate = store.predicateForIncompleteReminders(withDueDateStarting: nil, ending: nil, calendars: nil)
    let semaphore = DispatchSemaphore(value: 0)
    store.fetchReminders(matching: predicate) { reminders in
        for reminder in reminders ?? [] {
            let components = reminder.dueDateComponents
            let hasTime = components?.hour != nil || components?.minute != nil || components?.second != nil
            let due: AnyCodable
            if hasTime, let date = components?.date { due = .integer(epoch(date)) } else { due = .null }
            let dueDate: AnyCodable
            if let components = components, let year = components.year, let month = components.month, let day = components.day {
                dueDate = .string(String(format: "%04d-%02d-%02d", year, month, day))
            } else { dueDate = .null }
            reminderItems.append([
                "id": .string(reminder.calendarItemIdentifier),
                "title": .string(reminder.title ?? ""),
                "due": due,
                "due_date": dueDate,
                "has_time": .bool(hasTime),
                "completed": .bool(reminder.isCompleted),
                "list": .string(reminder.calendar.title),
                "priority": .integer(Int64(reminder.priority))
            ])
        }
        semaphore.signal()
    }
    semaphore.wait()
}

let payload = Payload(
    calendar: SourceResult(ok: calendarAccess.0, error: calendarAccess.1, items: calendarItems),
    reminders: SourceResult(ok: reminderAccess.0, error: reminderAccess.1, items: reminderItems)
)
let encoder = JSONEncoder()
encoder.outputFormatting = [.sortedKeys]
FileHandle.standardOutput.write(try encoder.encode(payload))
