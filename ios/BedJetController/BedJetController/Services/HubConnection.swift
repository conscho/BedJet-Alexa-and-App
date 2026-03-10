import Foundation
import Combine

/// Manages connection to the BedJet Hub server via WebSocket and REST API.
@MainActor
class HubConnection: ObservableObject {
    @Published var status: BedJetStatus = .disconnected
    @Published var isConnected = false
    @Published var connectionError: String?

    private var webSocketTask: URLSessionWebSocketTask?
    private var session = URLSession.shared
    private var hubURL: URL

    init(hubHost: String = "bedjet-hub.local", hubPort: Int = 8265) {
        self.hubURL = URL(string: "http://\(hubHost):\(hubPort)")!
    }

    func updateHubAddress(host: String, port: Int) {
        self.hubURL = URL(string: "http://\(host):\(port)")!
    }

    // MARK: - WebSocket

    func connectWebSocket() {
        let wsURL = URL(string: "ws://\(hubURL.host ?? "localhost"):\(hubURL.port ?? 8265)/ws")!
        webSocketTask = session.webSocketTask(with: wsURL)
        webSocketTask?.resume()
        isConnected = true
        connectionError = nil
        receiveMessage()
    }

    func disconnectWebSocket() {
        webSocketTask?.cancel(with: .goingAway, reason: nil)
        webSocketTask = nil
        isConnected = false
        status = .disconnected
    }

    private func receiveMessage() {
        webSocketTask?.receive { [weak self] result in
            Task { @MainActor in
                guard let self = self else { return }
                switch result {
                case .success(let message):
                    switch message {
                    case .string(let text):
                        self.handleMessage(text)
                    case .data(let data):
                        if let text = String(data: data, encoding: .utf8) {
                            self.handleMessage(text)
                        }
                    @unknown default:
                        break
                    }
                    self.receiveMessage()

                case .failure(let error):
                    self.connectionError = error.localizedDescription
                    self.isConnected = false
                    // Attempt reconnection after 3 seconds
                    try? await Task.sleep(nanoseconds: 3_000_000_000)
                    self.connectWebSocket()
                }
            }
        }
    }

    private func handleMessage(_ text: String) {
        guard let data = text.data(using: .utf8) else { return }
        do {
            let decoder = JSONDecoder()
            let msg = try decoder.decode(WSMessage.self, from: data)
            if msg.type == "status", let statusData = msg.data {
                self.status = statusData
            }
        } catch {
            print("Failed to decode WebSocket message: \(error)")
        }
    }

    // Send command via WebSocket
    func sendWSCommand(_ command: [String: Any]) {
        guard let data = try? JSONSerialization.data(withJSONObject: command),
              let text = String(data: data, encoding: .utf8) else { return }
        webSocketTask?.send(.string(text)) { error in
            if let error = error {
                print("WebSocket send error: \(error)")
            }
        }
    }

    // MARK: - REST API Commands

    func setMode(_ mode: BedJetMode) async {
        sendWSCommand(["command": "set_mode", "mode": mode.apiValue])
    }

    func turnOff() async {
        sendWSCommand(["command": "set_mode", "mode": "off"])
    }

    func setTemperature(_ tempF: Double) async {
        sendWSCommand(["command": "set_temperature", "temperature_f": tempF])
    }

    func setFanSpeed(_ percent: Int) async {
        sendWSCommand(["command": "set_fan", "percent": percent])
    }

    func setRuntime(hours: Int, minutes: Int) async {
        sendWSCommand(["command": "set_runtime", "hours": hours, "minutes": minutes])
    }

    func setPreset(_ number: Int) async {
        sendWSCommand(["command": "set_mode", "mode": "m\(number)"])
    }

    // MARK: - REST Fallback

    private func post(_ endpoint: String, body: [String: Any]) async throws {
        let url = hubURL.appendingPathComponent(endpoint)
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        let (_, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse,
              (200...299).contains(httpResponse.statusCode) else {
            throw URLError(.badServerResponse)
        }
    }
}
