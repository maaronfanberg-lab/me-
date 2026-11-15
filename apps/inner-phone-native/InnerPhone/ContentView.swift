import SwiftUI
import UIKit

struct ContentView: View {
    @State private var number = ""
    @State private var callFailed = false

    private let keys: [[String]] = [
        ["1", "2", "3"],
        ["4", "5", "6"],
        ["7", "8", "9"],
        ["+", "0", "⌫"]
    ]

    var body: some View {
        ZStack {
            LinearGradient(
                colors: [Color.black, Color(red: 0.08, green: 0.09, blue: 0.10)],
                startPoint: .top,
                endPoint: .bottom
            )
            .ignoresSafeArea()

            VStack(spacing: 22) {
                Spacer(minLength: 12)

                VStack(spacing: 5) {
                    Text("INNER PHONE")
                        .font(.system(size: 13, weight: .semibold, design: .monospaced))
                        .tracking(4)
                        .foregroundStyle(.secondary)

                    Text(number.isEmpty ? "—" : number)
                        .font(.system(size: 37, weight: .light, design: .rounded))
                        .foregroundStyle(.white)
                        .minimumScaleFactor(0.55)
                        .lineLimit(1)
                        .frame(maxWidth: .infinity)
                        .padding(.horizontal, 22)
                        .padding(.vertical, 20)
                        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 24, style: .continuous))
                        .accessibilityLabel(number.isEmpty ? "No number entered" : "Number \(number)")
                }

                VStack(spacing: 14) {
                    ForEach(keys, id: \.self) { row in
                        HStack(spacing: 14) {
                            ForEach(row, id: \.self) { key in
                                Button {
                                    press(key)
                                } label: {
                                    Text(key)
                                        .font(.system(size: key == "⌫" ? 26 : 30, weight: .regular, design: .rounded))
                                        .foregroundStyle(.white)
                                        .frame(width: 82, height: 66)
                                        .background(
                                            RoundedRectangle(cornerRadius: 22, style: .continuous)
                                                .fill(Color.white.opacity(0.10))
                                        )
                                }
                                .buttonStyle(.plain)
                                .accessibilityLabel(key == "⌫" ? "Delete" : key)
                            }
                        }
                    }
                }

                Button {
                    placeCall()
                } label: {
                    HStack(spacing: 10) {
                        Image(systemName: "phone.fill")
                        Text("CALL")
                            .tracking(2)
                    }
                    .font(.system(size: 18, weight: .semibold, design: .rounded))
                    .foregroundStyle(.black)
                    .frame(maxWidth: .infinity)
                    .frame(height: 62)
                    .background(Color.white, in: RoundedRectangle(cornerRadius: 22, style: .continuous))
                }
                .buttonStyle(.plain)
                .disabled(cleanNumber.isEmpty)
                .opacity(cleanNumber.isEmpty ? 0.35 : 1)

                Text("No contacts. No address-book permission. Enter a number manually.")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)

                Spacer(minLength: 10)
            }
            .padding(.horizontal, 28)
        }
        .preferredColorScheme(.dark)
        .alert("Call unavailable", isPresented: $callFailed) {
            Button("OK", role: .cancel) { }
        } message: {
            Text("This device could not hand the number to a calling app.")
        }
    }

    private var cleanNumber: String {
        var result = ""
        for (index, character) in number.enumerated() {
            if character.isNumber {
                result.append(character)
            } else if character == "+" && index == 0 {
                result.append(character)
            }
        }
        return result
    }

    private func press(_ key: String) {
        switch key {
        case "⌫":
            if !number.isEmpty { number.removeLast() }
        case "+":
            if number.isEmpty { number.append("+") }
        default:
            if number.count < 24 { number.append(key) }
        }
    }

    private func placeCall() {
        let digits = cleanNumber
        guard !digits.isEmpty,
              let encoded = digits.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed),
              let url = URL(string: "tel:\(encoded)") else {
            callFailed = true
            return
        }

        UIApplication.shared.open(url, options: [:]) { success in
            if !success {
                callFailed = true
            }
        }
    }
}

#Preview {
    ContentView()
}
