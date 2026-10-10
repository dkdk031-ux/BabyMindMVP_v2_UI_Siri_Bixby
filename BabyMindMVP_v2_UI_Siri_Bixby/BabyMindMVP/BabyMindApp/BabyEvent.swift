import Foundation
import SwiftData

@Model
final class BabyEvent {
    var id: UUID
    var type: String
    var startedAt: Date
    var endedAt: Date?
    var amount: Double?
    var unit: String?
    var note: String?

    init(type: String, startedAt: Date, endedAt: Date? = nil, amount: Double? = nil, unit: String? = nil, note: String? = nil) {
        self.id = UUID(); self.type = type; self.startedAt = startedAt; self.endedAt = endedAt
        self.amount = amount; self.unit = unit; self.note = note
    }
}
