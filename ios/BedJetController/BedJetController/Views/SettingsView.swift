import SwiftUI

struct SettingsView: View {
    @ObservedObject var hub: HubConnection
    @Environment(\.dismiss) private var dismiss
    @State private var hubHost = "bedjet-hub.local"
    @State private var hubPort = "8265"

    var body: some View {
        NavigationStack {
            Form {
                Section("Hub Connection") {
                    TextField("Hub Host", text: $hubHost)
                        .textContentType(.URL)
                        .autocapitalization(.none)
                        .disableAutocorrection(true)
                    TextField("Hub Port", text: $hubPort)
                        .keyboardType(.numberPad)

                    Button("Update Connection") {
                        let port = Int(hubPort) ?? 8265
                        hub.updateHubAddress(host: hubHost, port: port)
                        hub.disconnectWebSocket()
                        hub.connectWebSocket()
                    }
                    .disabled(hubHost.isEmpty)
                }

                Section("Connection Status") {
                    HStack {
                        Text("Hub")
                        Spacer()
                        Text(hub.isConnected ? "Connected" : "Disconnected")
                            .foregroundStyle(hub.isConnected ? .green : .red)
                    }
                    HStack {
                        Text("BedJet")
                        Spacer()
                        Text(hub.status.isConnected ? "Connected" : "Disconnected")
                            .foregroundStyle(hub.status.isConnected ? .green : .red)
                    }
                    if let error = hub.connectionError {
                        Text(error)
                            .font(.caption)
                            .foregroundStyle(.red)
                    }
                }
            }
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }
}
