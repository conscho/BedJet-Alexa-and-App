import SwiftUI

struct ContentView: View {
    @StateObject private var hub = HubConnection()
    @State private var showSettings = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 20) {
                    // Connection status banner
                    ConnectionBanner(hub: hub)

                    if hub.status.isConnected {
                        // Current status
                        StatusCard(status: hub.status)

                        // Mode selector
                        ModeSelector(hub: hub, currentMode: hub.status.bedJetMode)

                        // Temperature control
                        TemperatureControl(hub: hub, currentTemp: hub.status.targetTempF)

                        // Fan speed control
                        FanControl(hub: hub, currentFan: hub.status.fanPercent)

                        // Timer
                        TimerControl(hub: hub, status: hub.status)

                        // Presets
                        PresetButtons(hub: hub)
                    }
                }
                .padding()
            }
            .navigationTitle("BedJet")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: { showSettings = true }) {
                        Image(systemName: "gear")
                    }
                }
            }
            .sheet(isPresented: $showSettings) {
                SettingsView(hub: hub)
            }
        }
        .onAppear {
            hub.connectWebSocket()
        }
    }
}

// MARK: - Connection Banner

struct ConnectionBanner: View {
    @ObservedObject var hub: HubConnection

    var body: some View {
        HStack {
            Image(systemName: hub.isConnected ? "wifi" : "wifi.slash")
                .foregroundStyle(hub.isConnected ? .green : .red)
            Text(hub.isConnected ? "Connected to Hub" : "Disconnected")
                .font(.subheadline)
                .foregroundStyle(hub.isConnected ? .secondary : .red)

            Spacer()

            if !hub.isConnected {
                Button("Reconnect") {
                    hub.connectWebSocket()
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.small)
            }
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(hub.isConnected ? Color.green.opacity(0.1) : Color.red.opacity(0.1))
        )
    }
}

// MARK: - Status Card

struct StatusCard: View {
    let status: BedJetStatus

    var body: some View {
        VStack(spacing: 16) {
            // Mode badge
            HStack {
                Image(systemName: status.bedJetMode.icon)
                    .font(.title2)
                Text(status.mode)
                    .font(.title2.bold())
            }
            .foregroundStyle(modeColor)

            // Temperature display
            HStack(spacing: 30) {
                VStack {
                    Text("\(Int(status.actualTempF))°")
                        .font(.system(size: 48, weight: .thin, design: .rounded))
                    Text("Current")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                if status.bedJetMode != .standby {
                    Image(systemName: "arrow.right")
                        .foregroundStyle(.secondary)

                    VStack {
                        Text("\(Int(status.targetTempF))°")
                            .font(.system(size: 48, weight: .thin, design: .rounded))
                            .foregroundStyle(modeColor)
                        Text("Target")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
            }

            // Additional info
            HStack(spacing: 20) {
                Label("\(status.fanPercent)%", systemImage: "fan.fill")
                Label("Room \(Int(status.ambientTempF))°", systemImage: "thermometer")
                if status.bedJetMode != .standby {
                    Label(status.timeRemaining, systemImage: "timer")
                }
            }
            .font(.caption)
            .foregroundStyle(.secondary)
        }
        .padding()
        .frame(maxWidth: .infinity)
        .background(
            RoundedRectangle(cornerRadius: 16)
                .fill(.ultraThinMaterial)
        )
    }

    var modeColor: Color {
        switch status.bedJetMode {
        case .heat, .turbo, .extendedHeat: return .orange
        case .cool: return .blue
        case .dry: return .teal
        default: return .gray
        }
    }
}

// MARK: - Mode Selector

struct ModeSelector: View {
    @ObservedObject var hub: HubConnection
    let currentMode: BedJetMode

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Mode")
                .font(.headline)

            HStack(spacing: 12) {
                // Power off button
                Button {
                    Task { await hub.turnOff() }
                } label: {
                    VStack(spacing: 4) {
                        Image(systemName: "power")
                            .font(.title3)
                        Text("Off")
                            .font(.caption2)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 12)
                    .background(
                        RoundedRectangle(cornerRadius: 12)
                            .fill(currentMode == .standby ? Color.gray.opacity(0.3) : Color.clear)
                            .strokeBorder(Color.gray.opacity(0.3), lineWidth: 1)
                    )
                }
                .foregroundStyle(currentMode == .standby ? .primary : .secondary)

                // Mode buttons
                ForEach(BedJetMode.selectableModes, id: \.rawValue) { mode in
                    Button {
                        Task { await hub.setMode(mode) }
                    } label: {
                        VStack(spacing: 4) {
                            Image(systemName: mode.icon)
                                .font(.title3)
                            Text(mode.displayName)
                                .font(.caption2)
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 12)
                        .background(
                            RoundedRectangle(cornerRadius: 12)
                                .fill(currentMode == mode ? modeColor(mode).opacity(0.3) : Color.clear)
                                .strokeBorder(modeColor(mode).opacity(0.3), lineWidth: 1)
                        )
                    }
                    .foregroundStyle(currentMode == mode ? modeColor(mode) : .secondary)
                }
            }
        }
    }

    func modeColor(_ mode: BedJetMode) -> Color {
        switch mode {
        case .heat, .turbo, .extendedHeat: return .orange
        case .cool: return .blue
        case .dry: return .teal
        default: return .gray
        }
    }
}

// MARK: - Temperature Control

struct TemperatureControl: View {
    @ObservedObject var hub: HubConnection
    let currentTemp: Double
    @State private var targetTemp: Double = 72

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Temperature")
                    .font(.headline)
                Spacer()
                Text("\(Int(targetTemp))°F")
                    .font(.title3.monospacedDigit())
                    .foregroundStyle(.orange)
            }

            HStack {
                Text("66°")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Slider(value: $targetTemp, in: 66...109, step: 1) { editing in
                    if !editing {
                        Task { await hub.setTemperature(targetTemp) }
                    }
                }
                .tint(.orange)
                Text("109°")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            HStack {
                Button {
                    targetTemp = max(66, targetTemp - 1)
                    Task { await hub.setTemperature(targetTemp) }
                } label: {
                    Image(systemName: "minus.circle.fill")
                        .font(.title2)
                }

                Spacer()

                Button {
                    targetTemp = min(109, targetTemp + 1)
                    Task { await hub.setTemperature(targetTemp) }
                } label: {
                    Image(systemName: "plus.circle.fill")
                        .font(.title2)
                }
            }
            .foregroundStyle(.orange)
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 16)
                .fill(.ultraThinMaterial)
        )
        .onAppear { targetTemp = currentTemp > 0 ? currentTemp : 72 }
        .onChange(of: currentTemp) { _, newValue in
            if newValue > 0 { targetTemp = newValue }
        }
    }
}

// MARK: - Fan Control

struct FanControl: View {
    @ObservedObject var hub: HubConnection
    let currentFan: Int
    @State private var fanSpeed: Double = 50

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Fan Speed")
                    .font(.headline)
                Spacer()
                Text("\(Int(fanSpeed))%")
                    .font(.title3.monospacedDigit())
                    .foregroundStyle(.blue)
            }

            HStack {
                Text("5%")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Slider(value: $fanSpeed, in: 5...100, step: 5) { editing in
                    if !editing {
                        Task { await hub.setFanSpeed(Int(fanSpeed)) }
                    }
                }
                .tint(.blue)
                Text("100%")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 16)
                .fill(.ultraThinMaterial)
        )
        .onAppear { fanSpeed = currentFan > 0 ? Double(currentFan) : 50 }
        .onChange(of: currentFan) { _, newValue in
            if newValue > 0 { fanSpeed = Double(newValue) }
        }
    }
}

// MARK: - Timer Control

struct TimerControl: View {
    @ObservedObject var hub: HubConnection
    let status: BedJetStatus
    @State private var hours = 0
    @State private var minutes = 0

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Timer")
                    .font(.headline)
                Spacer()
                if status.bedJetMode != .standby {
                    Text(status.timeRemaining)
                        .font(.title3.monospacedDigit())
                        .foregroundStyle(.green)
                }
            }

            HStack {
                Picker("Hours", selection: $hours) {
                    ForEach(0...10, id: \.self) { h in
                        Text("\(h)h").tag(h)
                    }
                }
                .pickerStyle(.wheel)
                .frame(width: 80, height: 100)

                Picker("Minutes", selection: $minutes) {
                    ForEach(Array(stride(from: 0, through: 55, by: 5)), id: \.self) { m in
                        Text("\(m)m").tag(m)
                    }
                }
                .pickerStyle(.wheel)
                .frame(width: 80, height: 100)

                Spacer()

                Button("Set") {
                    Task { await hub.setRuntime(hours: hours, minutes: minutes) }
                }
                .buttonStyle(.borderedProminent)
            }
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 16)
                .fill(.ultraThinMaterial)
        )
    }
}

// MARK: - Preset Buttons

struct PresetButtons: View {
    @ObservedObject var hub: HubConnection

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Presets")
                .font(.headline)

            HStack(spacing: 12) {
                ForEach(1...3, id: \.self) { num in
                    Button {
                        Task { await hub.setPreset(num) }
                    } label: {
                        Text("M\(num)")
                            .font(.headline)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 16)
                            .background(
                                RoundedRectangle(cornerRadius: 12)
                                    .strokeBorder(Color.purple.opacity(0.5), lineWidth: 1.5)
                            )
                    }
                    .foregroundStyle(.purple)
                }
            }
        }
    }
}

#Preview {
    ContentView()
}
