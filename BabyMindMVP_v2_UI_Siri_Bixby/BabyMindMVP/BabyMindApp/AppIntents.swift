import AppIntents
import Foundation

struct QuickLogIntent: AppIntent {
    static var title: LocalizedStringResource = "베이비 기록"
    static var description = IntentDescription("말로 전달한 육아 기록을 BabyMind AI에 저장합니다.")
    static var openAppWhenRun = true

    @Parameter(title: "기록 내용", requestValueDialog: IntentDialog("무엇을 기록할까요? 예: 분유 180 먹었어"))
    var text: String

    func perform() async throws -> some IntentResult & ProvidesDialog {
        let result = try await APIClient.shared.parse(text)
        let payload = try JSONEncoder().encode(result)
        UserDefaults.standard.set(payload, forKey: "pendingSiriEvents")
        UserDefaults.standard.set(Date(), forKey: "pendingSiriEventsDate")
        return .result(dialog: "\(result.events.count)개 기록을 준비했어요. BabyMind에서 저장할게요.")
    }
}

struct AskBabyMindIntent: AppIntent {
    static var title: LocalizedStringResource = "베이비마인드에게 질문"
    static var description = IntentDescription("BabyMind를 열어 AI 질문을 시작합니다.")
    static var openAppWhenRun = true

    @Parameter(title: "질문", requestValueDialog: IntentDialog("무엇이 궁금한가요?"))
    var question: String

    func perform() async throws -> some IntentResult & ProvidesDialog {
        UserDefaults.standard.set(question, forKey: "pendingQuestion")
        return .result(dialog: "BabyMind에서 확인할게요.")
    }
}

struct BabyMindShortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(intent: QuickLogIntent(), phrases: [
            "\(.applicationName)에 기록해",
            "\(.applicationName) 육아 기록",
            "\(.applicationName)에 아기 기록"
        ], shortTitle: "육아 기록", systemImageName: "mic.fill")

        AppShortcut(intent: AskBabyMindIntent(), phrases: [
            "\(.applicationName)에게 물어봐",
            "\(.applicationName) 아기 기록 물어봐"
        ], shortTitle: "AI 질문", systemImageName: "sparkles")
    }
}
