import Foundation

/// BedJet operating modes
enum BedJetMode: Int, Codable, CaseIterable {
    case standby = 0
    case heat = 1
    case turbo = 2
    case extendedHeat = 3
    case cool = 4
    case dry = 5
    case wait = 6

    var displayName: String {
        switch self {
        case .standby: return "Off"
        case .heat: return "Heat"
        case .turbo: return "Turbo"
        case .extendedHeat: return "Ext Heat"
        case .cool: return "Cool"
        case .dry: return "Dry"
        case .wait: return "Wait"
        }
    }

    var apiValue: String {
        switch self {
        case .standby: return "off"
        case .heat: return "heat"
        case .turbo: return "turbo"
        case .extendedHeat: return "extended_heat"
        case .cool: return "cool"
        case .dry: return "dry"
        case .wait: return "off"
        }
    }

    var icon: String {
        switch self {
        case .standby: return "power"
        case .heat: return "flame.fill"
        case .turbo: return "flame"
        case .extendedHeat: return "flame.fill"
        case .cool: return "wind"
        case .dry: return "drop.triangle"
        case .wait: return "clock"
        }
    }

    var color: String {
        switch self {
        case .standby: return "gray"
        case .heat, .turbo, .extendedHeat: return "orange"
        case .cool: return "blue"
        case .dry: return "teal"
        case .wait: return "yellow"
        }
    }

    /// Modes that users can select (excludes standby and wait)
    static var selectableModes: [BedJetMode] {
        [.heat, .cool, .turbo, .dry, .extendedHeat]
    }
}

/// Status response from the hub server
struct BedJetStatus: Codable {
    let mode: String
    let modeValue: Int
    let targetTempF: Double
    let actualTempF: Double
    let ambientTempF: Double
    let targetTempC: Double
    let actualTempC: Double
    let fanPercent: Int
    let fanStep: Int
    let timeRemaining: String
    let timeRemainingHours: Int
    let timeRemainingMinutes: Int
    let timeRemainingSeconds: Int
    let isConnected: Bool

    enum CodingKeys: String, CodingKey {
        case mode
        case modeValue = "mode_value"
        case targetTempF = "target_temp_f"
        case actualTempF = "actual_temp_f"
        case ambientTempF = "ambient_temp_f"
        case targetTempC = "target_temp_c"
        case actualTempC = "actual_temp_c"
        case fanPercent = "fan_percent"
        case fanStep = "fan_step"
        case timeRemaining = "time_remaining"
        case timeRemainingHours = "time_remaining_hours"
        case timeRemainingMinutes = "time_remaining_minutes"
        case timeRemainingSeconds = "time_remaining_seconds"
        case isConnected = "is_connected"
    }

    var bedJetMode: BedJetMode {
        BedJetMode(rawValue: modeValue) ?? .standby
    }

    static let disconnected = BedJetStatus(
        mode: "Disconnected",
        modeValue: 0,
        targetTempF: 0,
        actualTempF: 0,
        ambientTempF: 0,
        targetTempC: 0,
        actualTempC: 0,
        fanPercent: 0,
        fanStep: 0,
        timeRemaining: "0:00:00",
        timeRemainingHours: 0,
        timeRemainingMinutes: 0,
        timeRemainingSeconds: 0,
        isConnected: false
    )
}

/// WebSocket message wrapper
struct WSMessage: Codable {
    let type: String
    let data: BedJetStatus?
    let message: String?
}
