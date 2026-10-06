import AuthenticationServices
import CryptoKit
import Foundation
import Security
import UIKit

struct SoundCloudToken: Codable {
    let accessToken: String
    let refreshToken: String
    let expiresIn: TimeInterval
    let scope: String?
    let tokenType: String?
    let issuedAt: Date

    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case refreshToken = "refresh_token"
        case expiresIn = "expires_in"
        case scope
        case tokenType = "token_type"
        case issuedAt
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        accessToken = try c.decode(String.self, forKey: .accessToken)
        refreshToken = try c.decode(String.self, forKey: .refreshToken)
        expiresIn = try c.decode(TimeInterval.self, forKey: .expiresIn)
        scope = try c.decodeIfPresent(String.self, forKey: .scope)
        tokenType = try c.decodeIfPresent(String.self, forKey: .tokenType)
        issuedAt = try c.decodeIfPresent(Date.self, forKey: .issuedAt) ?? Date()
    }

    init(accessToken: String, refreshToken: String, expiresIn: TimeInterval, scope: String?, tokenType: String?, issuedAt: Date = Date()) {
        self.accessToken = accessToken
        self.refreshToken = refreshToken
        self.expiresIn = expiresIn
        self.scope = scope
        self.tokenType = tokenType
        self.issuedAt = issuedAt
    }

    var shouldRefresh: Bool {
        Date().addingTimeInterval(300) >= issuedAt.addingTimeInterval(expiresIn)
    }
}

private struct SoundCloudBrokerConfiguration: Decodable {
    let clientID: String
    let redirectURI: String
    let authorizeURL: URL

    enum CodingKeys: String, CodingKey {
        case clientID = "client_id"
        case redirectURI = "redirect_uri"
        case authorizeURL = "authorize_url"
    }
}

private struct SoundCloudTokenPayload: Decodable {
    let accessToken: String
    let refreshToken: String
    let expiresIn: TimeInterval
    let scope: String?
    let tokenType: String?

    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case refreshToken = "refresh_token"
        case expiresIn = "expires_in"
        case scope
        case tokenType = "token_type"
    }
}

@MainActor
final class SoundCloudAccount: NSObject, ObservableObject, ASWebAuthenticationPresentationContextProviding {
    enum AccountError: LocalizedError {
        case brokerNotConfigured
        case invalidBrokerResponse
        case authorizationDidNotStart
        case invalidCallback
        case stateMismatch
        case missingAuthorizationCode
        case http(Int, String)
        case noToken

        var errorDescription: String? {
            switch self {
            case .brokerNotConfigured:
                return "Set SoundCloudBrokerBaseURL in Info.plist to the deployed OAuth Worker URL."
            case .invalidBrokerResponse:
                return "The SoundCloud OAuth broker returned an invalid response."
            case .authorizationDidNotStart:
                return "The SoundCloud authorization session could not start."
            case .invalidCallback:
                return "SoundCloud returned an invalid callback URL."
            case .stateMismatch:
                return "SoundCloud sign-in state verification failed."
            case .missingAuthorizationCode:
                return "SoundCloud did not return an authorization code."
            case .http(let status, let message):
                return "SoundCloud authentication failed (HTTP \(status)): \(message)"
            case .noToken:
                return "No SoundCloud account is signed in."
            }
        }
    }

    @Published private(set) var isAuthenticated = false
    @Published private(set) var status = "Not signed in to SoundCloud."

    private let tokenKey = "soundcloud.oauth.token"
    private var token: SoundCloudToken?
    private var webSession: ASWebAuthenticationSession?

    override init() {
        super.init()
        do {
            token = try KeychainStore.load(SoundCloudToken.self, account: tokenKey)
            isAuthenticated = token != nil
            if isAuthenticated { status = "SoundCloud account token loaded from Keychain." }
        } catch {
            status = "Could not read SoundCloud credentials from Keychain."
        }
    }

    func signIn() async {
        do {
            let config = try await fetchBrokerConfiguration()
            let verifier = Self.randomURLSafeString(byteCount: 32)
            let challenge = Self.pkceChallenge(for: verifier)
            let state = Self.randomURLSafeString(byteCount: 24)

            var components = URLComponents(url: config.authorizeURL, resolvingAgainstBaseURL: false)
            components?.queryItems = [
                URLQueryItem(name: "client_id", value: config.clientID),
                URLQueryItem(name: "redirect_uri", value: config.redirectURI),
                URLQueryItem(name: "response_type", value: "code"),
                URLQueryItem(name: "code_challenge", value: challenge),
                URLQueryItem(name: "code_challenge_method", value: "S256"),
                URLQueryItem(name: "state", value: state),
                URLQueryItem(name: "display", value: "popup")
            ]

            guard let authorizationURL = components?.url,
                  let callbackScheme = URL(string: config.redirectURI)?.scheme else {
                throw AccountError.invalidBrokerResponse
            }

            status = "Opening SoundCloud sign-in…"
            let callback = try await runWebAuthentication(url: authorizationURL, callbackScheme: callbackScheme)
            guard let callbackComponents = URLComponents(url: callback, resolvingAgainstBaseURL: false) else {
                throw AccountError.invalidCallback
            }

            let callbackState = callbackComponents.queryItems?.first(where: { $0.name == "state" })?.value
            guard callbackState == state else { throw AccountError.stateMismatch }

            guard let code = callbackComponents.queryItems?.first(where: { $0.name == "code" })?.value,
                  !code.isEmpty else {
                throw AccountError.missingAuthorizationCode
            }

            let newToken = try await exchangeCode(
                code,
                verifier: verifier,
                redirectURI: config.redirectURI
            )
            try persist(newToken)
            status = "Signed in to SoundCloud."
        } catch is CancellationError {
            status = "SoundCloud sign-in cancelled."
        } catch let error as ASWebAuthenticationSessionError where error.code == .canceledLogin {
            status = "SoundCloud sign-in cancelled."
        } catch {
            status = error.localizedDescription
        }
    }

    func signOut() {
        webSession?.cancel()
        webSession = nil
        token = nil
        isAuthenticated = false
        do {
            try KeychainStore.delete(account: tokenKey)
            status = "Signed out locally."
        } catch {
            status = "Signed out, but Keychain cleanup failed."
        }
    }

    func validAccessToken() async throws -> String {
        guard var current = token else { throw AccountError.noToken }
        if current.shouldRefresh {
            current = try await refresh(current)
            try persist(current)
        }
        return current.accessToken
    }

    func presentationAnchor(for session: ASWebAuthenticationSession) -> ASPresentationAnchor {
        let scenes = UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }
        if let window = scenes.flatMap(\.windows).first(where: { $0.isKeyWindow }) {
            return window
        }
        if let firstScene = scenes.first {
            return UIWindow(windowScene: firstScene)
        }
        return UIWindow(frame: .zero)
    }

    private func persist(_ newToken: SoundCloudToken) throws {
        try KeychainStore.save(newToken, account: tokenKey)
        token = newToken
        isAuthenticated = true
    }

    private func fetchBrokerConfiguration() async throws -> SoundCloudBrokerConfiguration {
        let base = try brokerBaseURL()
        let url = base.appending(path: "config")
        let (data, response) = try await URLSession.shared.data(from: url)
        try validate(response: response, data: data)
        return try JSONDecoder().decode(SoundCloudBrokerConfiguration.self, from: data)
    }

    private func exchangeCode(_ code: String, verifier: String, redirectURI: String) async throws -> SoundCloudToken {
        let base = try brokerBaseURL()
        return try await requestToken(
            endpoint: base.appending(path: "oauth/exchange"),
            body: [
                "code": code,
                "code_verifier": verifier,
                "redirect_uri": redirectURI
            ]
        )
    }

    private func refresh(_ current: SoundCloudToken) async throws -> SoundCloudToken {
        let base = try brokerBaseURL()
        return try await requestToken(
            endpoint: base.appending(path: "oauth/refresh"),
            body: ["refresh_token": current.refreshToken]
        )
    }

    private func requestToken(endpoint: URL, body: [String: String]) async throws -> SoundCloudToken {
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.httpBody = try JSONEncoder().encode(body)

        let (data, response) = try await URLSession.shared.data(for: request)
        try validate(response: response, data: data)
        let payload = try JSONDecoder().decode(SoundCloudTokenPayload.self, from: data)
        return SoundCloudToken(
            accessToken: payload.accessToken,
            refreshToken: payload.refreshToken,
            expiresIn: payload.expiresIn,
            scope: payload.scope,
            tokenType: payload.tokenType
        )
    }

    private func validate(response: URLResponse, data: Data) throws {
        guard let http = response as? HTTPURLResponse else {
            throw AccountError.invalidBrokerResponse
        }
        guard (200..<300).contains(http.statusCode) else {
            let message = String(data: data, encoding: .utf8) ?? "Unknown error"
            throw AccountError.http(http.statusCode, message)
        }
    }

    private func brokerBaseURL() throws -> URL {
        guard let string = Bundle.main.object(forInfoDictionaryKey: "SoundCloudBrokerBaseURL") as? String,
              !string.contains("YOUR-WORKERS-SUBDOMAIN"),
              let url = URL(string: string),
              url.scheme == "https" else {
            throw AccountError.brokerNotConfigured
        }
        return url
    }

    private func runWebAuthentication(url: URL, callbackScheme: String) async throws -> URL {
        try await withCheckedThrowingContinuation { continuation in
            let session = ASWebAuthenticationSession(url: url, callbackURLScheme: callbackScheme) { [weak self] callbackURL, error in
                Task { @MainActor in
                    self?.webSession = nil
                    if let error {
                        continuation.resume(throwing: error)
                    } else if let callbackURL {
                        continuation.resume(returning: callbackURL)
                    } else {
                        continuation.resume(throwing: AccountError.invalidCallback)
                    }
                }
            }
            session.presentationContextProvider = self
            session.prefersEphemeralWebBrowserSession = false
            webSession = session
            guard session.start() else {
                webSession = nil
                continuation.resume(throwing: AccountError.authorizationDidNotStart)
                return
            }
        }
    }

    private static func randomURLSafeString(byteCount: Int) -> String {
        var bytes = [UInt8](repeating: 0, count: byteCount)
        let result = SecRandomCopyBytes(kSecRandomDefault, byteCount, &bytes)
        precondition(result == errSecSuccess)
        return Data(bytes).base64URLEncodedString()
    }

    private static func pkceChallenge(for verifier: String) -> String {
        let digest = SHA256.hash(data: Data(verifier.utf8))
        return Data(digest).base64URLEncodedString()
    }
}

private extension Data {
    func base64URLEncodedString() -> String {
        base64EncodedString()
            .replacingOccurrences(of: "+", with: "-")
            .replacingOccurrences(of: "/", with: "_")
            .replacingOccurrences(of: "=", with: "")
    }
}
