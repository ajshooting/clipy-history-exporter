// swift-tools-version: 6.1
// The swift-tools-version declares the minimum version of Swift required to build this package.

import PackageDescription

let package = Package(
    name: "RealmExporter",
    dependencies: [
        .package(url: "https://github.com/realm/realm-swift.git", .exact("10.7.2"))
    ],
    targets: [
        // Targets are the basic building blocks of a package, defining a module or a test suite.
        // Targets can depend on other targets in this package and products from dependencies.
        .executableTarget(
            name: "RealmExporter",
            dependencies: [
                .product(name: "RealmSwift", package: "realm-swift")
            ])
    ]
)
