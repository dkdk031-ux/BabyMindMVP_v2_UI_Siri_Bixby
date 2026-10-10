import SwiftUI
import SwiftData

struct ContentView: View {
    @Environment(\.modelContext) private var context
    @Query(sort: \BabyEvent.startedAt, order: .reverse) private var events: [BabyEvent]
    @StateObject private var speech = SpeechRecognizer()
    @State private var text = ""
    @State private var status = "말하거나 입력해 주세요"
    @State private var answer = ""
    @State private var busy = false
    @State private var selectedTab = 0

    private var today: [BabyEvent] { events.filter { Calendar.current.isDateInToday($0.startedAt) } }
    private var todayFormula: Int { Int(today.filter{$0.type == "formula"}.compactMap{$0.amount}.reduce(0,+)) }
    private var todaySleep: Int { Int(today.filter{$0.type == "sleep"}.compactMap { e in e.endedAt.map{$0.timeIntervalSince(e.startedAt)/60} }.reduce(0,+)) }
    private var todayDiaper: Int { today.filter{$0.type == "diaper"}.count }

    var body: some View {
        TabView(selection: $selectedTab) {
            NavigationStack { home }.tabItem { Label("오늘", systemImage: "house.fill") }.tag(0)
            NavigationStack { timeline }.tabItem { Label("기록", systemImage: "list.bullet.rectangle") }.tag(1)
            NavigationStack { aiView }.tabItem { Label("AI", systemImage: "sparkles") }.tag(2)
        }
        .tint(.indigo)
        .task { await speech.requestPermission(); consumeExternalActions() }
        .onAppear { consumeExternalActions() }
    }

    private var home: some View {
        ScrollView {
            VStack(spacing: 18) {
                HStack { VStack(alignment:.leading, spacing:4) { Text("BabyMind").font(.largeTitle.bold()); Text("오늘도 잘하고 있어요").foregroundStyle(.secondary) }; Spacer(); Image(systemName:"person.crop.circle.fill").font(.largeTitle).foregroundStyle(.indigo) }
                .padding(.horizontal)

                HStack(spacing:10) {
                    stat("🍼", "분유", "\(todayFormula) ml")
                    stat("😴", "수면", "\(todaySleep)분")
                    stat("🧷", "기저귀", "\(todayDiaper)회")
                }.padding(.horizontal)

                VStack(alignment:.leading, spacing:12) {
                    HStack { Text("최근 기록").font(.headline); Spacer(); Button("전체보기") { selectedTab = 1 }.font(.caption) }
                    ForEach(today.prefix(5)) { e in eventRow(e) }
                    if today.isEmpty { ContentUnavailableView("아직 기록이 없어요", systemImage:"heart.text.square", description: Text("아래 마이크를 눌러 첫 기록을 남겨보세요.")) }
                }.padding().background(.background).clipShape(RoundedRectangle(cornerRadius:22)).shadow(color:.black.opacity(0.05), radius:12).padding(.horizontal)

                voiceCard
            }.padding(.vertical)
        }.background(Color(.systemGroupedBackground)).navigationBarHidden(true)
    }

    private func stat(_ icon:String,_ title:String,_ value:String) -> some View {
        VStack(spacing:7) { Text(icon).font(.title2); Text(value).font(.headline); Text(title).font(.caption).foregroundStyle(.secondary) }
            .frame(maxWidth:.infinity).padding(.vertical,14).background(.background).clipShape(RoundedRectangle(cornerRadius:18))
    }

    private var voiceCard: some View {
        VStack(spacing:14) {
            Text(speech.isRecording ? "듣고 있어요…" : "그냥 말해주세요").font(.headline)
            Text(speech.isRecording ? speech.transcript : "“방금 분유 180 먹었어”\n“7시부터 8시 반까지 잤어”").multilineTextAlignment(.center).font(.subheadline).foregroundStyle(.secondary)
            Button { Task { await toggleSpeech() } } label: {
                ZStack { Circle().fill(speech.isRecording ? Color.red : Color.indigo).frame(width:78,height:78).shadow(radius:8); Image(systemName:speech.isRecording ? "stop.fill" : "mic.fill").font(.system(size:30)).foregroundStyle(.white) }
            }
            Text(status).font(.caption).foregroundStyle(.secondary)
            HStack { quick("🍼","분유 180") ; quick("💩","응가했어"); quick("😴","지금 잠들었어") }
        }.frame(maxWidth:.infinity).padding(22).background(.background).clipShape(RoundedRectangle(cornerRadius:24)).padding(.horizontal)
    }

    private func quick(_ icon:String,_ value:String) -> some View { Button { Task { await parseAndSave(value) } } label: { VStack { Text(icon).font(.title2); Text(value.components(separatedBy:" ").first ?? value).font(.caption) }.frame(maxWidth:.infinity).padding(.vertical,10).background(Color(.secondarySystemGroupedBackground)).clipShape(RoundedRectangle(cornerRadius:14)) }.buttonStyle(.plain) }

    private var timeline: some View {
        List { Section("오늘") { ForEach(today) { e in eventRow(e) }.onDelete(perform: delete) } }.navigationTitle("육아 기록")
    }

    private var aiView: some View {
        VStack(spacing:16) {
            if answer.isEmpty { ContentUnavailableView("BabyMind AI", systemImage:"sparkles", description:Text("저장된 육아 기록을 바탕으로 질문해보세요.")) }
            else { ScrollView { Text(answer).frame(maxWidth:.infinity, alignment:.leading).padding().background(.thinMaterial).clipShape(RoundedRectangle(cornerRadius:18)).padding() } }
            Spacer()
            HStack { TextField("예: 오늘 총 얼마나 먹었어?", text:$text).textFieldStyle(.roundedBorder); Button { Task { await ask(text) } } label:{ Image(systemName:"arrow.up.circle.fill").font(.title) }.disabled(text.isEmpty || busy) }.padding()
        }.navigationTitle("AI에게 질문")
    }

    private func eventRow(_ e: BabyEvent) -> some View { HStack(spacing:12) { Text(icon(e.type)).font(.title2).frame(width:36,height:36).background(Color(.secondarySystemGroupedBackground)).clipShape(Circle()); VStack(alignment:.leading){ Text(label(e)).font(.subheadline.weight(.semibold)); if let n=e.note, !n.isEmpty { Text(n).font(.caption).foregroundStyle(.secondary) } }; Spacer(); Text(e.startedAt.formatted(date:.omitted,time:.shortened)).font(.caption).foregroundStyle(.secondary) }.padding(.vertical,3) }

    private func toggleSpeech() async { if speech.isRecording { speech.stop(); text=speech.transcript; await parseAndSave(text) } else { do { try speech.start() } catch { status=error.localizedDescription } } }
    private func parseAndSave(_ input:String) async { guard !input.trimmingCharacters(in:.whitespaces).isEmpty else{return}; busy=true; defer{busy=false}; do { let r=try await APIClient.shared.parse(input); save(r); status="✓ \(r.events.count)개 기록 완료"; text=""; answer="" } catch { status="오류: \(error.localizedDescription)" } }
    private func save(_ result:ParseResponse) { let iso=ISO8601DateFormatter(); for p in result.events { guard let start=iso.date(from:p.started_at) else{continue}; context.insert(BabyEvent(type:p.type, startedAt:start, endedAt:p.ended_at.flatMap(iso.date), amount:p.amount, unit:p.unit, note:p.note)) }; try? context.save() }
    private func ask(_ q:String) async { busy=true; defer{busy=false}; let iso=ISO8601DateFormatter(); let payload:[[String:Any]]=events.prefix(200).map{ e in var d:[String:Any]=["type":e.type,"started_at":iso.string(from:e.startedAt)]; if let a=e.amount{d["amount"]=a}; if let u=e.unit{d["unit"]=u}; if let n=e.note{d["note"]=n}; if let x=e.endedAt{d["ended_at"]=iso.string(from:x)}; return d }; do{answer=try await APIClient.shared.ask(q,events:payload); text=""}catch{status="오류: \(error.localizedDescription)"} }
    private func consumeExternalActions() { if let d=UserDefaults.standard.data(forKey:"pendingSiriEvents"), let r=try? JSONDecoder().decode(ParseResponse.self,from:d) { save(r); UserDefaults.standard.removeObject(forKey:"pendingSiriEvents"); status="✓ Siri 기록 저장 완료" }; if let q=UserDefaults.standard.string(forKey:"pendingQuestion") { UserDefaults.standard.removeObject(forKey:"pendingQuestion"); selectedTab=2; text=q; Task{await ask(q)} } }
    private func delete(_ offsets:IndexSet){for i in offsets{context.delete(today[i])}; try? context.save()}
    private func icon(_ t:String)->String{["formula":"🍼","breastfeed":"🤱","sleep":"😴","diaper":"🧷","meal":"🍚","medicine":"💊","temperature":"🌡️"][t] ?? "📝"}
    private func label(_ e:BabyEvent)->String{let names=["formula":"분유","breastfeed":"모유","sleep":"수면","diaper":"기저귀","meal":"식사","medicine":"약","temperature":"체온","memo":"메모"]; var s=names[e.type] ?? e.type; if let a=e.amount{s+=" \(a.rounded()==a ? String(Int(a)) : String(a))\(e.unit ?? "")"}; if let end=e.endedAt{s+=" · \(Int(end.timeIntervalSince(e.startedAt)/60))분"}; return s}
}
