import Cocoa
import Foundation

final class AppDelegate: NSObject, NSApplicationDelegate {
    private var serverProcess: Process?
    private var terminating = false
    private let url = URL(string: "http://127.0.0.1:8765/index.html")!

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)

        guard let resources = Bundle.main.resourceURL else {
            fatalAlert("The application resources could not be located.")
            return
        }

        let site = resources.appendingPathComponent("site", isDirectory: true)
        let server = site.appendingPathComponent("server.py", isDirectory: false)
        guard FileManager.default.fileExists(atPath: server.path) else {
            fatalAlert("server.py is missing from the offline concert house.")
            return
        }

        let command = pythonCommand()
        let process = Process()
        process.executableURL = URL(fileURLWithPath: command.executable)
        process.arguments = command.prefixArguments + [server.path]
        process.currentDirectoryURL = site

        var environment = ProcessInfo.processInfo.environment
        environment["THE12_NO_BROWSER"] = "1"
        process.environment = environment
        process.standardOutput = FileHandle.nullDevice
        process.standardError = FileHandle.nullDevice

        process.terminationHandler = { [weak self] child in
            DispatchQueue.main.async {
                guard let self, !self.terminating else { return }
                self.fatalAlert("The local emergency generator stopped unexpectedly (exit \(child.terminationStatus)).")
            }
        }

        do {
            try process.run()
            serverProcess = process
        } catch {
            fatalAlert("Python 3 could not start the local emergency generator.\n\n\(error.localizedDescription)")
            return
        }

        DispatchQueue.main.asyncAfter(deadline: .now() + 0.9) { [url] in
            guard ProcessInfo.processInfo.environment["THE12_NO_BROWSER"] != "1" else { return }
            NSWorkspace.shared.open(url)
        }
    }

    func applicationWillTerminate(_ notification: Notification) {
        terminating = true
        if let process = serverProcess, process.isRunning {
            process.terminate()
        }
    }

    private func pythonCommand() -> (executable: String, prefixArguments: [String]) {
        let fm = FileManager.default
        let direct = [
            "/usr/bin/python3",
            "/opt/homebrew/bin/python3",
            "/usr/local/bin/python3"
        ]
        for path in direct where fm.isExecutableFile(atPath: path) {
            return (path, [])
        }
        if fm.isExecutableFile(atPath: "/usr/bin/xcrun") {
            return ("/usr/bin/xcrun", ["python3"])
        }
        return ("/usr/bin/env", ["python3"])
    }

    private func fatalAlert(_ message: String) {
        let alert = NSAlert()
        alert.alertStyle = .critical
        alert.messageText = "The 12 Day Dancer"
        alert.informativeText = message
        alert.addButton(withTitle: "Quit")
        alert.runModal()
        terminating = true
        NSApp.terminate(nil)
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.run()
