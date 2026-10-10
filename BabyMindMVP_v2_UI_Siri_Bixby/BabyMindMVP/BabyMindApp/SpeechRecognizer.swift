import Foundation
import Speech
import AVFoundation

@MainActor
final class SpeechRecognizer: ObservableObject {
    @Published var transcript = ""
    @Published var isRecording = false
    private let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "ko-KR"))
    private let engine = AVAudioEngine()
    private var request: SFSpeechAudioBufferRecognitionRequest?
    private var task: SFSpeechRecognitionTask?

    func requestPermission() async {
        _ = await withCheckedContinuation { c in SFSpeechRecognizer.requestAuthorization { c.resume(returning: $0) } }
        _ = await AVAudioApplication.requestRecordPermission()
    }
    func start() throws {
        transcript = ""; task?.cancel(); request = SFSpeechAudioBufferRecognitionRequest()
        guard let request else { return }
        request.shouldReportPartialResults = true
        let node = engine.inputNode, format = node.outputFormat(forBus: 0)
        node.removeTap(onBus: 0)
        node.installTap(onBus: 0, bufferSize: 1024, format: format) { buffer, _ in request.append(buffer) }
        task = recognizer?.recognitionTask(with: request) { [weak self] result, _ in
            guard let result else { return }
            Task { @MainActor in self?.transcript = result.bestTranscription.formattedString }
        }
        engine.prepare(); try engine.start(); isRecording = true
    }
    func stop() { engine.stop(); engine.inputNode.removeTap(onBus: 0); request?.endAudio(); isRecording = false }
}
