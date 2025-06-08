import Foundation
import RealmSwift

class CPYClip: Object {
    override static func primaryKey() -> String? {
        return "dataHash"
    }
    @objc dynamic var dataHash: String = ""
    @objc dynamic var dataPath: String = ""
    @objc dynamic var title: String = ""
    @objc dynamic var primaryType: String = ""
    @objc dynamic var updateTime: Int = 0
    @objc dynamic var thumbnailPath: String = ""
    @objc dynamic var isColorCode: Bool = false
}

struct ClipMetadata: Codable {
    let dataHash: String, dataPath: String, title: String, primaryType: String, updateTime: Int, thumbnailPath: String, isColorCode: Bool
    let copiedRealmPath: String
}

func fail(with message: String) -> Never {
    fputs("Error: \(message)\n", stderr)
    exit(1)
}

// App Store版だと場所が違う...?
let originalRealmPathString = NSHomeDirectory() + "/Library/Application Support/com.clipy-app.Clipy/default.realm"
let originalRealmURL = URL(fileURLWithPath: originalRealmPathString)

let tempDir = FileManager.default.temporaryDirectory
let copiedRealmURL = tempDir.appendingPathComponent("clipy_temp_copy.realm")

do {
    // もし古いコピーファイルが残っていたら、まず削除
    if FileManager.default.fileExists(atPath: copiedRealmURL.path) {
        try FileManager.default.removeItem(at: copiedRealmURL)
    }

    // 元のDBファイルを一時的な場所にコピー
    try FileManager.default.copyItem(at: originalRealmURL, to: copiedRealmURL)

    var config = Realm.Configuration(
        fileURL: copiedRealmURL,
        schemaVersion: 23,
        objectTypes: [CPYClip.self]
    )

    let realm = try Realm(configuration: config)
    let clips = realm.objects(CPYClip.self).sorted(byKeyPath: "updateTime", ascending: false)

    let metadataList: [ClipMetadata] = clips.map { clip in
        return ClipMetadata(dataHash: clip.dataHash, dataPath: clip.dataPath, title: clip.title, primaryType: clip.primaryType, updateTime: clip.updateTime, thumbnailPath: clip.thumbnailPath, isColorCode: clip.isColorCode, copiedRealmPath: copiedRealmURL.path)
    }

    let encoder = JSONEncoder()
    encoder.outputFormatting = .prettyPrinted
    let jsonData = try encoder.encode(metadataList)

    if let jsonString = String(data: jsonData, encoding: .utf8) {
        print(jsonString)
    }

} catch {
    fail(with: "Failed to process the database. Details: \(error.localizedDescription)")
}