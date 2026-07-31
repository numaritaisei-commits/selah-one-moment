#!/usr/bin/env swift

import AudioToolbox
import AVFoundation
import Foundation
import Vision

private let expectedWidth: CGFloat = 1280
private let expectedHeight: CGFloat = 720
private let captureMinimum = 98.0
private let captureMaximum = 102.0
private let finalDuration = 165.0

private enum VerificationError: Error, CustomStringConvertible {
    case usage
    case failed(String)

    var description: String {
        switch self {
        case .usage:
            return "usage: swift video_assets/verify_final_video.swift --capture CLEAN_CAPTURE.mov | --final CLEAN_CAPTURE.mov FINAL.mp4"
        case .failed(let message):
            return message
        }
    }
}

private func requireRegularFile(_ url: URL) throws {
    guard FileManager.default.isReadableFile(atPath: url.path) else {
        throw VerificationError.failed("file is missing or unreadable: \(url.lastPathComponent)")
    }
    let values = try url.resourceValues(forKeys: [.isRegularFileKey, .isSymbolicLinkKey])
    guard values.isRegularFile == true, values.isSymbolicLink != true else {
        throw VerificationError.failed("symlinks and non-regular media are refused: \(url.lastPathComponent)")
    }
}

private func seconds(_ asset: AVAsset) throws -> Double {
    let value = CMTimeGetSeconds(asset.duration)
    guard value.isFinite, value > 0 else {
        throw VerificationError.failed("media duration is not finite and positive")
    }
    return value
}

private func effectiveSize(_ track: AVAssetTrack) -> CGSize {
    let transformed = CGRect(origin: .zero, size: track.naturalSize).applying(track.preferredTransform)
    return CGSize(width: abs(transformed.width), height: abs(transformed.height))
}

private func isSize(_ size: CGSize, width: CGFloat, height: CGFloat) -> Bool {
    abs(size.width - width) <= 0.5 && abs(size.height - height) <= 0.5
}

private func hasSubtype(_ track: AVAssetTrack, _ subtype: FourCharCode) -> Bool {
    track.formatDescriptions.contains { item in
        let description = item as! CMFormatDescription
        return CMFormatDescriptionGetMediaSubType(description) == subtype
    }
}

private func recognizedText(asset: AVAsset, at time: Double) throws -> String {
    let generator = AVAssetImageGenerator(asset: asset)
    generator.appliesPreferredTrackTransform = true
    generator.requestedTimeToleranceBefore = .zero
    generator.requestedTimeToleranceAfter = .zero
    var actual = CMTime.zero
    let image: CGImage
    do {
        image = try generator.copyCGImage(
            at: CMTime(seconds: time, preferredTimescale: 600),
            actualTime: &actual
        )
    } catch {
        throw VerificationError.failed("could not sample frame near \(String(format: "%.1f", time)) seconds")
    }
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = false
    request.recognitionLanguages = ["en-US"]
    request.minimumTextHeight = 0.007
    let handler = VNImageRequestHandler(cgImage: image, options: [:])
    do {
        try handler.perform([request])
    } catch {
        throw VerificationError.failed("local OCR failed near \(String(format: "%.1f", time)) seconds")
    }
    return (request.results ?? [])
        .compactMap { $0.topCandidates(1).first?.string }
        .joined(separator: "\n")
}

private func normalized(_ text: String) -> String {
    String(text.lowercased().unicodeScalars.filter { CharacterSet.alphanumerics.contains($0) })
}

private let emailExpression = try! NSRegularExpression(
    pattern: #"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}"#,
    options: [.caseInsensitive]
)
private let phoneCandidateExpression = try! NSRegularExpression(
    pattern: #"\+?[0-9][0-9 ()\-]{8,}[0-9]"#,
    options: []
)
private let longSecretExpression = try! NSRegularExpression(
    pattern: #"\b[A-Za-z0-9_\-]{32,}\b"#,
    options: []
)

private func containsMatch(_ expression: NSRegularExpression, text: String) -> Bool {
    let range = NSRange(text.startIndex..<text.endIndex, in: text)
    return expression.firstMatch(in: text, options: [], range: range) != nil
}

private func containsPhoneLikeValue(_ text: String) -> Bool {
    let range = NSRange(text.startIndex..<text.endIndex, in: text)
    return phoneCandidateExpression.matches(in: text, options: [], range: range).contains { match in
        guard let swiftRange = Range(match.range, in: text) else { return false }
        return text[swiftRange].filter(\.isNumber).count >= 10
    }
}

private func rejectSensitiveOrDraftText(_ text: String, label: String, time: Double) throws {
    let compact = normalized(text)
    let forbidden = [
        "fixtureonly",
        "noliveaupicapture",
        "donotpublish",
        "placeholder",
        "authorizationbearer",
        "clientsecret",
        "apikey",
        "accesstoken",
        "refreshtoken",
        "oauthcode",
    ]
    if forbidden.contains(where: compact.contains) {
        throw VerificationError.failed("\(label) contains a forbidden draft/credential label near \(String(format: "%.1f", time)) seconds")
    }
    if containsMatch(emailExpression, text: text) {
        throw VerificationError.failed("\(label) may expose an email address near \(String(format: "%.1f", time)) seconds")
    }
    if containsPhoneLikeValue(text) {
        throw VerificationError.failed("\(label) may expose a phone number near \(String(format: "%.1f", time)) seconds")
    }
    if containsMatch(longSecretExpression, text: text) {
        throw VerificationError.failed("\(label) contains a token-like long string near \(String(format: "%.1f", time)) seconds")
    }
}

private func requireTerms(
    _ terms: [String],
    asset: AVAsset,
    at time: Double,
    label: String
) throws {
    let text = try recognizedText(asset: asset, at: time)
    let compact = normalized(text)
    for term in terms {
        if !compact.contains(normalized(term)) {
            throw VerificationError.failed("\(label) is missing required reviewed text near \(String(format: "%.1f", time)) seconds")
        }
    }
}

private func scanFrames(asset: AVAsset, through end: Double, interval: Double, label: String) throws {
    var time = 0.0
    var count = 0
    while time < end {
        let text = try recognizedText(asset: asset, at: min(time, end - 0.05))
        try rejectSensitiveOrDraftText(text, label: label, time: time)
        count += 1
        time += interval
    }
    print("PASS \(label): \(count) sampled frames contain no recognized draft marker, email, phone, or token-like value")
}

private func scanMetadata(asset: AVAsset, label: String) throws {
    let strings = asset.commonMetadata.compactMap(\.stringValue)
    let joined = strings.joined(separator: "\n")
    if containsMatch(emailExpression, text: joined)
        || containsPhoneLikeValue(joined)
        || containsMatch(longSecretExpression, text: joined) {
        throw VerificationError.failed("\(label) metadata may contain PII or a token-like value")
    }
}

private func verifyCapture(_ url: URL) throws -> AVURLAsset {
    try requireRegularFile(url)
    let asset = AVURLAsset(url: url)
    let duration = try seconds(asset)
    guard duration >= captureMinimum, duration <= captureMaximum else {
        throw VerificationError.failed("capture must be 98–102 seconds")
    }
    let videos = asset.tracks(withMediaType: .video)
    guard videos.count == 1, let video = videos.first,
          isSize(effectiveSize(video), width: expectedWidth, height: expectedHeight) else {
        throw VerificationError.failed("capture must contain one 1280×720 video track")
    }
    guard asset.tracks(withMediaType: .audio).isEmpty else {
        throw VerificationError.failed("capture must contain no microphone or system-audio track")
    }
    try scanMetadata(asset: asset, label: "capture")
    try scanFrames(asset: asset, through: captureMinimum, interval: 2, label: "capture")
    try requireTerms(["fictional", "synthetic"], asset: asset, at: 5, label: "opening synthetic scenario")
    for sample in [44.0, 54.0, 64.0, 72.0] {
        try requireTerms(["live", "gloo", "youversion"], asset: asset, at: sample, label: "uninterrupted live badge")
    }
    try requireTerms(["view version on youversion"], asset: asset, at: 72, label: "YouVersion attribution card")
    print("PASS capture structure and OCR gates")
    return asset
}

private func verifyFinal(_ url: URL) throws -> AVURLAsset {
    try requireRegularFile(url)
    let asset = AVURLAsset(url: url)
    let duration = try seconds(asset)
    guard abs(duration - finalDuration) <= 0.15 else {
        throw VerificationError.failed("final runtime must be 165.0 seconds and never exceed 180 seconds")
    }
    let videos = asset.tracks(withMediaType: .video)
    let audios = asset.tracks(withMediaType: .audio)
    guard videos.count == 1, let video = videos.first,
          isSize(effectiveSize(video), width: expectedWidth, height: expectedHeight),
          hasSubtype(video, kCMVideoCodecType_H264) else {
        throw VerificationError.failed("final must contain one 1280×720 H.264 video track")
    }
    guard audios.count == 1, let audio = audios.first,
          hasSubtype(audio, kAudioFormatMPEG4AAC) else {
        throw VerificationError.failed("final must contain one AAC audio track")
    }
    try scanMetadata(asset: asset, label: "final")
    try scanFrames(asset: asset, through: finalDuration, interval: 5, label: "final")
    try requireTerms(["fictional scenario", "synthetic text"], asset: asset, at: 5, label: "caption cue 1")
    try requireTerms(["voluntary", "words remain untouched"], asset: asset, at: 20, label: "caption cue 3")
    try requireTerms(["gloo ai", "passage key", "question key"], asset: asset, at: 50, label: "caption cue 5")
    try requireTerms(["no ai rewrite", "no auto post"], asset: asset, at: 80, label: "caption cue 7")
    try requireTerms(["strict json", "exact enums", "fixed https hosts"], asset: asset, at: 110, label: "caption cue 9")
    try requireTerms(["37 / 37", "local safety tests passed"], asset: asset, at: 135, label: "caption cue 11")
    try requireTerms(["one moment before send", "public code", "public kaggle notebook"], asset: asset, at: 158, label: "caption cue 13")
    try requireTerms(["gloo", "youversion", "strict json"], asset: asset, at: 110, label: "architecture card")
    try requireTerms(["37/37", "engineering evidence"], asset: asset, at: 135, label: "evidence card")
    try requireTerms(["selah", "github", "kaggle"], asset: asset, at: 158, label: "end card")
    print("PASS final structure, codecs, OCR gates, and 165-second limit")
    return asset
}

do {
    if CommandLine.arguments.count == 3, CommandLine.arguments[1] == "--capture" {
        _ = try verifyCapture(URL(fileURLWithPath: CommandLine.arguments[2]).standardizedFileURL)
        print("AUTOMATED CAPTURE CHECKS PASSED — full visual review is still mandatory before building")
    } else if CommandLine.arguments.count == 4, CommandLine.arguments[1] == "--final" {
        _ = try verifyCapture(URL(fileURLWithPath: CommandLine.arguments[2]).standardizedFileURL)
        _ = try verifyFinal(URL(fileURLWithPath: CommandLine.arguments[3]).standardizedFileURL)
        print("AUTOMATED FINAL CHECKS PASSED — publication still requires the manual frame/audio checklist")
    } else {
        throw VerificationError.usage
    }
} catch {
    fputs("FAIL: \(error)\n", stderr)
    exit(1)
}
