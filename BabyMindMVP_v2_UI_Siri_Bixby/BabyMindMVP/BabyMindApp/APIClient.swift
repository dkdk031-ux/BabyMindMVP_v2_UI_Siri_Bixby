import Foundation

struct ParsedEvent: Codable {
    let type: String
    let started_at: String
    let ended_at: String?
    let amount: Double?
    let unit: String?
    let note: String?
}
struct ParseResponse: Codable { let events: [ParsedEvent] }
struct AskResponse: Codable { let answer: String }

final class APIClient {
    static let shared = APIClient()
    // 실제 iPhone 테스트 시 Mac의 LAN IP로 변경: http://192.168.x.x:8000
    var baseURL = URL(string: "http://127.0.0.1:8000")!

    func parse(_ text: String) async throws -> ParseResponse {
        var r = URLRequest(url: baseURL.appendingPathComponent("parse")); r.httpMethod = "POST"
        r.setValue("application/json", forHTTPHeaderField: "Content-Type")
        r.httpBody = try JSONSerialization.data(withJSONObject: ["text": text, "timezone": "Asia/Seoul"])
        let (d, resp) = try await URLSession.shared.data(for: r)
        try check(resp, d); return try JSONDecoder().decode(ParseResponse.self, from: d)
    }

    func ask(_ question: String, events: [[String: Any]]) async throws -> String {
        var r = URLRequest(url: baseURL.appendingPathComponent("ask")); r.httpMethod = "POST"
        r.setValue("application/json", forHTTPHeaderField: "Content-Type")
        r.httpBody = try JSONSerialization.data(withJSONObject: ["question": question, "events": events])
        let (d, resp) = try await URLSession.shared.data(for: r)
        try check(resp, d); return try JSONDecoder().decode(AskResponse.self, from: d).answer
    }
    private func check(_ response: URLResponse, _ data: Data) throws {
        guard let h = response as? HTTPURLResponse, (200..<300).contains(h.statusCode) else {
            throw NSError(domain: "BabyMindAPI", code: 1, userInfo: [NSLocalizedDescriptionKey: String(data: data, encoding: .utf8) ?? "API 오류"])
        }
    }
}
