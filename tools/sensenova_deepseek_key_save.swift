import AppKit
import Foundation
import Security

private let service = "cn.cz.novel-architecture.sensenova.deepseek-v4-flash"
private let account = "SENSENOVA_API_KEY"

private func fail(_ message: String, code: Int32 = 1) -> Never {
    FileHandle.standardError.write(Data((message + "\n").utf8))
    exit(code)
}

private func saveToKeychain(_ password: String) throws {
    let lookup: [String: Any] = [
        kSecClass as String: kSecClassGenericPassword,
        kSecAttrService as String: service,
        kSecAttrAccount as String: account,
    ]
    let passwordData = Data(password.utf8)
    let update: [String: Any] = [kSecValueData as String: passwordData]

    var status = SecItemUpdate(lookup as CFDictionary, update as CFDictionary)
    if status == errSecItemNotFound {
        var item = lookup
        item[kSecValueData as String] = passwordData
        status = SecItemAdd(item as CFDictionary, nil)
    }

    guard status == errSecSuccess else {
        let detail = SecCopyErrorMessageString(status, nil) as String? ?? "未知钥匙串错误"
        throw NSError(
            domain: NSOSStatusErrorDomain,
            code: Int(status),
            userInfo: [NSLocalizedDescriptionKey: detail]
        )
    }
}

let application = NSApplication.shared
application.setActivationPolicy(.accessory)
application.activate(ignoringOtherApps: true)

let alert = NSAlert()
alert.alertStyle = .informational
alert.messageText = "配置 DeepSeek V4 Flash"
alert.informativeText = "请输入 SenseNova API Key。钥匙只保存到本机 macOS 钥匙串，不会写入项目文件或 Git。"
alert.addButton(withTitle: "保存")
alert.addButton(withTitle: "取消")

let input = NSSecureTextField(frame: NSRect(x: 0, y: 0, width: 420, height: 24))
input.placeholderString = "SenseNova API Key"
alert.accessoryView = input
alert.window.initialFirstResponder = input

guard alert.runModal() == .alertFirstButtonReturn else {
    exit(2)
}

let password = input.stringValue.trimmingCharacters(in: .whitespacesAndNewlines)
guard !password.isEmpty else {
    fail("没有输入 API Key，未保存。")
}
guard !password.contains("\n") && !password.contains("\r") else {
    fail("API Key 不能包含换行，未保存。")
}

do {
    try saveToKeychain(password)
    print("已保存到 macOS 钥匙串；项目文件中没有密钥。")
} catch {
    fail("钥匙串写入失败：\(error.localizedDescription)")
}
