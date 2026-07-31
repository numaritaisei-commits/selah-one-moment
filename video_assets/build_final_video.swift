#!/usr/bin/env swift

import AppKit
import AVFoundation
import CoreVideo
import Foundation
import QuartzCore
import Vision

private let width = 1280
private let height = 720
private let captureSeconds = 98
private let timelineSeconds = 165
private let framesPerSecond = 30
private let cardFramesPerSecond = 1

private struct CardSegment {
    let start: Int
    let end: Int
    let imageName: String
}

private struct CaptionCue {
    let start: Double
    let end: Double
    let text: String
}

private enum BuildError: Error, CustomStringConvertible {
    case badArguments
    case invalidInput(String)
    case missingAsset(String)
    case writer(String)
    case export(String)

    var description: String {
        switch self {
        case .badArguments:
            return "usage: swift video_assets/build_final_video.swift CLEAN_LIVE_CAPTURE.mov OUTPUT.mp4"
        case .invalidInput(let message):
            return "invalid input: \(message)"
        case .missingAsset(let name):
            return "required asset is missing or unsafe: \(name)"
        case .writer(let message):
            return "video writer failed: \(message)"
        case .export(let message):
            return "export failed: \(message)"
        }
    }
}

private func requireRegularFile(_ url: URL) throws {
    guard FileManager.default.isReadableFile(atPath: url.path) else {
        throw BuildError.missingAsset(url.lastPathComponent)
    }
    let values = try url.resourceValues(forKeys: [.isRegularFileKey, .isSymbolicLinkKey])
    guard values.isRegularFile == true, values.isSymbolicLink != true else {
        throw BuildError.missingAsset(url.lastPathComponent)
    }
}

private func finiteDurationSeconds(_ asset: AVAsset, label: String) throws -> Double {
    let seconds = CMTimeGetSeconds(asset.duration)
    guard seconds.isFinite, seconds > 0 else {
        throw BuildError.invalidInput("\(label) has no finite positive duration")
    }
    return seconds
}

private func almostEqual(_ a: CGFloat, _ b: CGFloat, tolerance: CGFloat = 0.5) -> Bool {
    abs(a - b) <= tolerance
}

private func isIdentity(_ transform: CGAffineTransform) -> Bool {
    almostEqual(transform.a, 1, tolerance: 0.0001)
        && almostEqual(transform.b, 0, tolerance: 0.0001)
        && almostEqual(transform.c, 0, tolerance: 0.0001)
        && almostEqual(transform.d, 1, tolerance: 0.0001)
        && almostEqual(transform.tx, 0, tolerance: 0.0001)
        && almostEqual(transform.ty, 0, tolerance: 0.0001)
}

private func rejectKnownDraftFrames(_ asset: AVAsset) throws {
    let generator = AVAssetImageGenerator(asset: asset)
    generator.appliesPreferredTrackTransform = true
    generator.requestedTimeToleranceBefore = .zero
    generator.requestedTimeToleranceAfter = .zero
    for second in [5.0, 25.0, 50.0, 80.0] {
        var actual = CMTime.zero
        let image: CGImage
        do {
            image = try generator.copyCGImage(
                at: CMTime(seconds: second, preferredTimescale: 600),
                actualTime: &actual
            )
        } catch {
            throw BuildError.invalidInput("capture frame preflight failed")
        }
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .accurate
        request.usesLanguageCorrection = false
        let handler = VNImageRequestHandler(cgImage: image, options: [:])
        do {
            try handler.perform([request])
        } catch {
            throw BuildError.invalidInput("capture OCR preflight failed")
        }
        let text = (request.results ?? [])
            .compactMap { $0.topCandidates(1).first?.string }
            .joined()
            .lowercased()
            .unicodeScalars
            .filter { CharacterSet.alphanumerics.contains($0) }
        let compact = String(text)
        if ["fixtureonly", "noliveaupicapture", "donotpublish", "placeholder"].contains(where: compact.contains) {
            throw BuildError.invalidInput("capture contains a fixture/placeholder publication blocker")
        }
    }
}

private func validateCapture(_ url: URL) throws -> AVURLAsset {
    try requireRegularFile(url)
    let asset = AVURLAsset(url: url)
    let seconds = try finiteDurationSeconds(asset, label: "capture")
    guard seconds >= Double(captureSeconds), seconds <= Double(captureSeconds + 4) else {
        throw BuildError.invalidInput("capture must be 98–102 seconds; got \(String(format: "%.3f", seconds))")
    }
    let videoTracks = asset.tracks(withMediaType: .video)
    guard videoTracks.count == 1, let track = videoTracks.first else {
        throw BuildError.invalidInput("capture must contain exactly one video track")
    }
    guard asset.tracks(withMediaType: .audio).isEmpty else {
        throw BuildError.invalidInput("capture must be silent; disable microphone and system audio")
    }
    guard almostEqual(track.naturalSize.width, CGFloat(width)),
          almostEqual(track.naturalSize.height, CGFloat(height)),
          isIdentity(track.preferredTransform) else {
        throw BuildError.invalidInput("capture must be unrotated 1280×720")
    }
    try rejectKnownDraftFrames(asset)
    return asset
}

private func validateCard(_ url: URL) throws -> NSImage {
    try requireRegularFile(url)
    guard let image = NSImage(contentsOf: url),
          let representation = image.representations.first(where: { $0.pixelsWide > 0 && $0.pixelsHigh > 0 }),
          representation.pixelsWide == width,
          representation.pixelsHigh == height else {
        throw BuildError.invalidInput("\(url.lastPathComponent) must decode as 1280×720")
    }
    return image
}

private func timestampSeconds(_ value: String) throws -> Double {
    let normalized = value.trimmingCharacters(in: .whitespaces)
    let pieces = normalized.split(separator: ":", omittingEmptySubsequences: false)
    guard pieces.count == 3,
          let hours = Double(pieces[0]),
          let minutes = Double(pieces[1]) else {
        throw BuildError.invalidInput("caption timestamp is malformed")
    }
    let secondPieces = pieces[2].split(separator: ",", omittingEmptySubsequences: false)
    guard secondPieces.count == 2,
          let seconds = Double(secondPieces[0]),
          let milliseconds = Double(secondPieces[1]) else {
        throw BuildError.invalidInput("caption timestamp is malformed")
    }
    return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000
}

private func parseCaptions(_ url: URL) throws -> [CaptionCue] {
    try requireRegularFile(url)
    let raw = try String(contentsOf: url, encoding: .utf8)
        .replacingOccurrences(of: "\r\n", with: "\n")
        .trimmingCharacters(in: .whitespacesAndNewlines)
    var cues: [CaptionCue] = []
    for block in raw.components(separatedBy: "\n\n") {
        let lines = block.split(separator: "\n", omittingEmptySubsequences: false).map(String.init)
        guard lines.count >= 3, Int(lines[0]) != nil else {
            throw BuildError.invalidInput("caption block is malformed")
        }
        let timeParts = lines[1].components(separatedBy: " --> ")
        guard timeParts.count == 2 else {
            throw BuildError.invalidInput("caption range is malformed")
        }
        let start = try timestampSeconds(timeParts[0])
        let end = try timestampSeconds(timeParts[1])
        guard start >= 0, end > start, end <= Double(timelineSeconds) else {
            throw BuildError.invalidInput("caption range is outside the 165-second timeline")
        }
        if let previous = cues.last, start < previous.end {
            throw BuildError.invalidInput("caption ranges overlap or move backwards")
        }
        cues.append(CaptionCue(start: start, end: end, text: lines.dropFirst(2).joined(separator: "\n")))
    }
    guard cues.count == 13,
          abs((cues.first?.start ?? -1) - 0) <= 0.001,
          abs((cues.last?.end ?? -1) - Double(timelineSeconds)) <= 0.001 else {
        throw BuildError.invalidInput("captions must contain 13 monotonic cues spanning exactly 0:00–2:45")
    }
    let joined = cues.map(\.text).joined(separator: "\n")
    guard joined.contains("37 / 37"), !joined.contains("33 / 33") else {
        throw BuildError.invalidInput("captions must use the reviewed 37 / 37 result")
    }
    return cues
}

private func waitUntilReady(_ input: AVAssetWriterInput, writer: AVAssetWriter) throws {
    while !input.isReadyForMoreMediaData {
        if writer.status == .failed || writer.status == .cancelled {
            throw BuildError.writer(writer.error?.localizedDescription ?? "writer stopped while waiting")
        }
        Thread.sleep(forTimeInterval: 0.005)
    }
}

private func makePixelBuffer(pool: CVPixelBufferPool, image: NSImage) throws -> CVPixelBuffer {
    var maybeBuffer: CVPixelBuffer?
    let status = CVPixelBufferPoolCreatePixelBuffer(nil, pool, &maybeBuffer)
    guard status == kCVReturnSuccess, let buffer = maybeBuffer else {
        throw BuildError.writer("could not allocate a pixel buffer (\(status))")
    }
    CVPixelBufferLockBaseAddress(buffer, [])
    defer { CVPixelBufferUnlockBaseAddress(buffer, []) }
    guard let base = CVPixelBufferGetBaseAddress(buffer),
          let context = CGContext(
            data: base,
            width: width,
            height: height,
            bitsPerComponent: 8,
            bytesPerRow: CVPixelBufferGetBytesPerRow(buffer),
            space: CGColorSpaceCreateDeviceRGB(),
            bitmapInfo: CGImageAlphaInfo.premultipliedFirst.rawValue
          ) else {
        throw BuildError.writer("could not create the card drawing context")
    }
    context.setFillColor(NSColor.black.cgColor)
    context.fill(CGRect(x: 0, y: 0, width: width, height: height))
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(cgContext: context, flipped: false)
    image.draw(in: NSRect(x: 0, y: 0, width: width, height: height), from: .zero, operation: .copy, fraction: 1)
    NSGraphicsContext.restoreGraphicsState()
    return buffer
}

private func clonePixelBuffer(pool: CVPixelBufferPool, source: CVPixelBuffer) throws -> CVPixelBuffer {
    var maybeBuffer: CVPixelBuffer?
    let status = CVPixelBufferPoolCreatePixelBuffer(nil, pool, &maybeBuffer)
    guard status == kCVReturnSuccess, let destination = maybeBuffer else {
        throw BuildError.writer("could not allocate a frame buffer (\(status))")
    }
    CVPixelBufferLockBaseAddress(source, .readOnly)
    CVPixelBufferLockBaseAddress(destination, [])
    defer {
        CVPixelBufferUnlockBaseAddress(destination, [])
        CVPixelBufferUnlockBaseAddress(source, .readOnly)
    }
    guard let sourceBase = CVPixelBufferGetBaseAddress(source),
          let destinationBase = CVPixelBufferGetBaseAddress(destination) else {
        throw BuildError.writer("pixel buffer has no base address")
    }
    let sourceBytes = CVPixelBufferGetBytesPerRow(source) * CVPixelBufferGetHeight(source)
    let destinationBytes = CVPixelBufferGetBytesPerRow(destination) * CVPixelBufferGetHeight(destination)
    guard sourceBytes == destinationBytes else {
        throw BuildError.writer("pixel-buffer byte sizes do not match")
    }
    memcpy(destinationBase, sourceBase, sourceBytes)
    return destination
}

private func renderCards(to outputURL: URL, assetsDirectory: URL) throws {
    let segments = [
        CardSegment(start: 0, end: 30, imageName: "architecture-card.png"),
        CardSegment(start: 30, end: 53, imageName: "evidence-card.png"),
        CardSegment(start: 53, end: 67, imageName: "end-card.png"),
    ]
    var images: [String: NSImage] = [:]
    for segment in segments where images[segment.imageName] == nil {
        images[segment.imageName] = try validateCard(assetsDirectory.appendingPathComponent(segment.imageName))
    }

    let writer = try AVAssetWriter(outputURL: outputURL, fileType: .mp4)
    writer.shouldOptimizeForNetworkUse = true
    let input = AVAssetWriterInput(
        mediaType: .video,
        outputSettings: [
            AVVideoCodecKey: AVVideoCodecType.h264,
            AVVideoWidthKey: width,
            AVVideoHeightKey: height,
            AVVideoCompressionPropertiesKey: [
                AVVideoAverageBitRateKey: 2_500_000,
                AVVideoExpectedSourceFrameRateKey: cardFramesPerSecond,
                AVVideoMaxKeyFrameIntervalKey: cardFramesPerSecond,
                AVVideoProfileLevelKey: AVVideoProfileLevelH264HighAutoLevel,
            ],
        ]
    )
    input.expectsMediaDataInRealTime = false
    let adaptor = AVAssetWriterInputPixelBufferAdaptor(
        assetWriterInput: input,
        sourcePixelBufferAttributes: [
            kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32ARGB,
            kCVPixelBufferWidthKey as String: width,
            kCVPixelBufferHeightKey as String: height,
        ]
    )
    guard writer.canAdd(input) else { throw BuildError.writer("H.264 input cannot be added") }
    writer.add(input)
    guard writer.startWriting() else {
        throw BuildError.writer(writer.error?.localizedDescription ?? "startWriting returned false")
    }
    writer.startSession(atSourceTime: .zero)
    guard let pool = adaptor.pixelBufferPool else {
        throw BuildError.writer("pixel-buffer pool was not created")
    }

    var templates: [Int: CVPixelBuffer] = [:]
    for segment in segments {
        guard let image = images[segment.imageName] else {
            throw BuildError.missingAsset(segment.imageName)
        }
        templates[segment.start] = try makePixelBuffer(pool: pool, image: image)
    }
    var retainedFrames: [CVPixelBuffer] = []
    retainedFrames.reserveCapacity(67)
    for second in 0..<67 {
        guard let segment = segments.first(where: { second >= $0.start && second < $0.end }),
              let template = templates[segment.start] else {
            throw BuildError.writer("card timeline has no frame at second \(second)")
        }
        try waitUntilReady(input, writer: writer)
        let buffer = try clonePixelBuffer(pool: pool, source: template)
        guard adaptor.append(buffer, withPresentationTime: CMTime(value: CMTimeValue(second), timescale: 1)) else {
            throw BuildError.writer(writer.error?.localizedDescription ?? "card append failed")
        }
        retainedFrames.append(buffer)
    }
    input.markAsFinished()
    writer.endSession(atSourceTime: CMTime(value: 67, timescale: 1))
    let semaphore = DispatchSemaphore(value: 0)
    writer.finishWriting { semaphore.signal() }
    semaphore.wait()
    guard writer.status == .completed else {
        throw BuildError.writer(writer.error?.localizedDescription ?? "card writer did not complete")
    }
}

private func makeCaptionImage(_ text: String) throws -> CGImage {
    let imageSize = NSSize(width: 1192, height: 56)
    let image = NSImage(size: imageSize)
    image.lockFocus()
    NSColor(calibratedWhite: 0.02, alpha: 0.96).setFill()
    NSBezierPath(roundedRect: NSRect(origin: .zero, size: imageSize), xRadius: 9, yRadius: 9).fill()
    let paragraph = NSMutableParagraphStyle()
    paragraph.alignment = .center
    paragraph.lineBreakMode = .byWordWrapping
    (text as NSString).draw(
        in: NSRect(x: 18, y: 7, width: 1156, height: 45),
        withAttributes: [
            .font: NSFont.systemFont(ofSize: 20, weight: .semibold),
            .foregroundColor: NSColor.white,
            .paragraphStyle: paragraph,
        ]
    )
    image.unlockFocus()
    guard let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        throw BuildError.writer("could not render a caption image")
    }
    return cgImage
}

private func makeVideoComposition(track: AVCompositionTrack, captions: [CaptionCue]) throws -> AVMutableVideoComposition {
    let composition = AVMutableVideoComposition()
    composition.renderSize = CGSize(width: width, height: height)
    composition.frameDuration = CMTime(value: 1, timescale: CMTimeScale(framesPerSecond))
    let instruction = AVMutableVideoCompositionInstruction()
    instruction.timeRange = CMTimeRange(start: .zero, duration: CMTime(value: CMTimeValue(timelineSeconds), timescale: 1))
    let layerInstruction = AVMutableVideoCompositionLayerInstruction(assetTrack: track)
    layerInstruction.setTransform(.identity, at: .zero)
    instruction.layerInstructions = [layerInstruction]
    composition.instructions = [instruction]

    // Keep captions in a dedicated band. The source picture is uniformly reduced
    // to 90%, so no caption can cover the live badge, passage, or attribution.
    let parentLayer = CALayer()
    parentLayer.frame = CGRect(x: 0, y: 0, width: width, height: height)
    parentLayer.backgroundColor = NSColor.black.cgColor
    let videoLayer = CALayer()
    videoLayer.frame = CGRect(x: 64, y: 72, width: 1152, height: 648)
    parentLayer.addSublayer(videoLayer)

    // The SRT has no gaps, so one always-visible text layer with a discrete
    // string animation is more deterministic than 13 overlapping opacity
    // animations during AVFoundation export.
    let captionImages = try captions.map { try makeCaptionImage($0.text) }
    let textLayer = CALayer()
    textLayer.frame = CGRect(x: 44, y: 8, width: 1192, height: 56)
    textLayer.contents = captionImages[0]
    textLayer.contentsGravity = .resizeAspect
    textLayer.masksToBounds = true
    textLayer.opacity = 1

    let captionText = CAKeyframeAnimation(keyPath: "contents")
    captionText.beginTime = AVCoreAnimationBeginTimeAtZero
    captionText.duration = Double(timelineSeconds)
    captionText.values = captionImages + [captionImages.last!]
    captionText.keyTimes = captions.map { NSNumber(value: $0.start / Double(timelineSeconds)) } + [1]
    captionText.calculationMode = .discrete
    captionText.fillMode = .both
    captionText.isRemovedOnCompletion = false
    textLayer.add(captionText, forKey: "captionText")
    parentLayer.addSublayer(textLayer)
    composition.animationTool = AVVideoCompositionCoreAnimationTool(
        postProcessingAsVideoLayer: videoLayer,
        in: parentLayer
    )
    return composition
}

private func assemble(
    captureAsset: AVURLAsset,
    cardsURL: URL,
    voiceURL: URL,
    captions: [CaptionCue],
    outputURL: URL
) throws {
    let cardsAsset = AVURLAsset(url: cardsURL)
    let voiceAsset = AVURLAsset(url: voiceURL)
    let composition = AVMutableComposition()
    guard let sourceCapture = captureAsset.tracks(withMediaType: .video).first,
          let sourceCards = cardsAsset.tracks(withMediaType: .video).first,
          let destinationVideo = composition.addMutableTrack(
            withMediaType: .video,
            preferredTrackID: kCMPersistentTrackID_Invalid
          ) else {
        throw BuildError.invalidInput("a required video track is missing")
    }
    let captureDuration = CMTime(value: CMTimeValue(captureSeconds), timescale: 1)
    let cardsDuration = CMTime(value: 67, timescale: 1)
    try destinationVideo.insertTimeRange(
        CMTimeRange(start: .zero, duration: captureDuration),
        of: sourceCapture,
        at: .zero
    )
    try destinationVideo.insertTimeRange(
        CMTimeRange(start: .zero, duration: cardsDuration),
        of: sourceCards,
        at: captureDuration
    )

    try requireRegularFile(voiceURL)
    let voiceSeconds = try finiteDurationSeconds(voiceAsset, label: "voiceover")
    guard voiceSeconds <= Double(timelineSeconds),
          let sourceAudio = voiceAsset.tracks(withMediaType: .audio).first,
          let destinationAudio = composition.addMutableTrack(
            withMediaType: .audio,
            preferredTrackID: kCMPersistentTrackID_Invalid
          ) else {
        throw BuildError.invalidInput("voiceover must contain one audio track no longer than 165 seconds")
    }
    let sourceAudioDuration = sourceAudio.timeRange.duration
    try destinationAudio.insertTimeRange(
        CMTimeRange(start: .zero, duration: sourceAudioDuration),
        of: sourceAudio,
        at: .zero
    )
    destinationAudio.scaleTimeRange(
        CMTimeRange(start: .zero, duration: sourceAudioDuration),
        toDuration: CMTime(value: CMTimeValue(timelineSeconds), timescale: 1)
    )

    guard let exporter = AVAssetExportSession(asset: composition, presetName: AVAssetExportPresetHighestQuality) else {
        throw BuildError.export("export session could not be created")
    }
    exporter.outputURL = outputURL
    exporter.outputFileType = .mp4
    exporter.shouldOptimizeForNetworkUse = true
    exporter.videoComposition = try makeVideoComposition(track: destinationVideo, captions: captions)
    exporter.audioTimePitchAlgorithm = .spectral
    exporter.timeRange = CMTimeRange(
        start: .zero,
        duration: CMTime(value: CMTimeValue(timelineSeconds), timescale: 1)
    )
    exporter.metadata = []
    let semaphore = DispatchSemaphore(value: 0)
    exporter.exportAsynchronously { semaphore.signal() }
    semaphore.wait()
    guard exporter.status == .completed else {
        throw BuildError.export(exporter.error?.localizedDescription ?? "final export did not complete")
    }
}

do {
    guard CommandLine.arguments.count == 3 else { throw BuildError.badArguments }
    let scriptURL = URL(fileURLWithPath: #filePath).standardizedFileURL
    let assetsDirectory = scriptURL.deletingLastPathComponent()
    let captureURL = URL(fileURLWithPath: CommandLine.arguments[1]).standardizedFileURL
    let outputURL = URL(fileURLWithPath: CommandLine.arguments[2]).standardizedFileURL
    guard outputURL.pathExtension.lowercased() == "mp4",
          !FileManager.default.fileExists(atPath: outputURL.path),
          captureURL != outputURL else {
        throw BuildError.invalidInput("output must be a new .mp4 path distinct from the capture")
    }
    let captureAsset = try validateCapture(captureURL)
    let captions = try parseCaptions(assetsDirectory.deletingLastPathComponent().appendingPathComponent("VIDEO_CAPTIONS.srt"))
    let voiceURL = assetsDirectory.appendingPathComponent("selah-voiceover-fallback.aiff")
    let temporaryCardsURL = FileManager.default.temporaryDirectory
        .appendingPathComponent("selah-final-cards-\(UUID().uuidString).mp4")
    defer { try? FileManager.default.removeItem(at: temporaryCardsURL) }
    try renderCards(to: temporaryCardsURL, assetsDirectory: assetsDirectory)
    try assemble(
        captureAsset: captureAsset,
        cardsURL: temporaryCardsURL,
        voiceURL: voiceURL,
        captions: captions,
        outputURL: outputURL
    )
    print("Created 165-second captioned final candidate: \(outputURL.lastPathComponent)")
} catch {
    fputs("error: \(error)\n", stderr)
    exit(1)
}
