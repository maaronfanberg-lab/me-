import Foundation

struct SoundCloudUser: Decodable, Hashable {
    let username: String
    let permalinkURL: String?

    enum CodingKeys: String, CodingKey {
        case username
        case permalinkURL = "permalink_url"
    }
}

struct SoundCloudTrack: Decodable, Identifiable, Hashable {
    let urn: String?
    let numericID: Int?
    let title: String
    let artworkURL: String?
    let permalinkURL: String?
    let access: String?
    let user: SoundCloudUser

    enum CodingKeys: String, CodingKey {
        case urn
        case numericID = "id"
        case title
        case artworkURL = "artwork_url"
        case permalinkURL = "permalink_url"
        case access
        case user
    }

    var resourceURN: String? {
        if let urn, !urn.isEmpty { return urn }
        if let numericID { return "soundcloud:tracks:\(numericID)" }
        return nil
    }

    var id: String {
        resourceURN ?? permalinkURL ?? "\(user.username):\(title)"
    }
}

struct SoundCloudPlaylist: Decodable, Identifiable, Hashable {
    let urn: String?
    let numericID: Int?
    let title: String
    let permalinkURL: String?
    let artworkURL: String?
    let tracks: [SoundCloudTrack]?
    let user: SoundCloudUser

    enum CodingKeys: String, CodingKey {
        case urn
        case numericID = "id"
        case title
        case permalinkURL = "permalink_url"
        case artworkURL = "artwork_url"
        case tracks
        case user
    }

    var id: String {
        urn ?? numericID.map(String.init) ?? permalinkURL ?? "\(user.username):\(title)"
    }
}

private struct SoundCloudCollectionPage<Element: Decodable>: Decodable {
    let collection: [Element]
    let nextHref: String?

    enum CodingKeys: String, CodingKey {
        case collection
        case nextHref = "next_href"
    }
}

private struct SoundCloudStreams: Decodable {
    let hlsAAC160URL: URL?
    let hlsAAC96URL: URL?

    enum CodingKeys: String, CodingKey {
        case hlsAAC160URL = "hls_aac_160_url"
        case hlsAAC96URL = "hls_aac_96_url"
    }
}

@MainActor
final class SoundCloudLibrary: ObservableObject {
    enum APIError: LocalizedError {
        case badResponse
        case http(Int, String)
        case unplayableTrack
        case missingTrackURN
        case noAACStream
        case untrustedTokenDestination
        case unresolvedAuthenticatedStream

        var errorDescription: String? {
            switch self {
            case .badResponse:
                return "SoundCloud returned an invalid response."
            case .http(let status, let message):
                return "SoundCloud API failed (HTTP \(status)): \(message)"
            case .unplayableTrack:
                return "This SoundCloud track is not playable for the current account."
            case .missingTrackURN:
                return "This track does not contain a usable SoundCloud resource URN."
            case .noAACStream:
                return "SoundCloud did not provide an AAC HLS stream for this track."
            case .untrustedTokenDestination:
                return "Refused to send the SoundCloud OAuth token to a URL outside https://api.soundcloud.com."
            case .unresolvedAuthenticatedStream:
                return "The SoundCloud HLS endpoint still requires an authorization header after resolution, so AVPlayer cannot safely consume it yet."
            }
        }
    }

    @Published private(set) var likedTracks: [SoundCloudTrack] = []
    @Published private(set) var playlists: [SoundCloudPlaylist] = []
    @Published private(set) var isLoading = false
    @Published private(set) var status = "SoundCloud library not loaded."

    func refresh(accessToken: String) async {
        isLoading = true
        defer { isLoading = false }

        do {
            async let likes = fetchAllTracks(
                initialPath: "/me/likes/tracks?limit=50&linked_partitioning=true",
                accessToken: accessToken,
                maximumItems: 200
            )
            async let sets = fetchAllPlaylists(
                initialPath: "/me/playlists?show_tracks=true&limit=25&linked_partitioning=true",
                accessToken: accessToken,
                maximumItems: 100
            )

            let (newLikes, newPlaylists) = try await (likes, sets)
            likedTracks = newLikes
            playlists = newPlaylists
            status = "Loaded \(newLikes.count) Likes and \(newPlaylists.count) playlists."
        } catch {
            status = error.localizedDescription
        }
    }

    func resolvePlayableHLS(for track: SoundCloudTrack, accessToken: String) async throws -> URL {
        if track.access == "blocked" { throw APIError.unplayableTrack }
        guard let urn = track.resourceURN else { throw APIError.missingTrackURN }

        let encodedURN = urn.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? urn
        let streams: SoundCloudStreams = try await apiGET(
            absoluteOrRelative: "/tracks/\(encodedURN)/streams",
            accessToken: accessToken
        )
        guard let authenticatedStreamURL = streams.hlsAAC160URL ?? streams.hlsAAC96URL else {
            throw APIError.noAACStream
        }

        // This request contains an OAuth bearer-equivalent credential. Never trust a
        // server-returned absolute URL blindly, even when it is expected to be SoundCloud.
        try requireTrustedSoundCloudAPIURL(authenticatedStreamURL)

        // The modern /streams response points back at an authenticated SoundCloud
        // streaming endpoint. Resolve that small HLS request with URLSession so its
        // OAuth header is applied, then hand the final signed CDN URL to AVPlayer.
        // This avoids AVURLAssetHTTPHeaderFieldsKey, which Apple explicitly says is unsupported.
        var request = URLRequest(url: authenticatedStreamURL)
        request.httpMethod = "GET"
        request.setValue("OAuth \(accessToken)", forHTTPHeaderField: "Authorization")
        request.setValue("application/vnd.apple.mpegurl, application/x-mpegURL, */*", forHTTPHeaderField: "Accept")

        let (_, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw APIError.badResponse }
        guard (200..<300).contains(http.statusCode) else {
            throw APIError.http(http.statusCode, "stream resolution failed")
        }
        guard let finalURL = response.url,
              finalURL.scheme?.lowercased() == "https" else {
            throw APIError.badResponse
        }

        let host = finalURL.host?.lowercased() ?? ""
        if host == "api.soundcloud.com" {
            // Do not pass an OAuth-dependent URL to AVPlayer: there is no supported
            // general Authorization-header initialization option for AVURLAsset.
            throw APIError.unresolvedAuthenticatedStream
        }
        return finalURL
    }

    private func fetchAllTracks(
        initialPath: String,
        accessToken: String,
        maximumItems: Int
    ) async throws -> [SoundCloudTrack] {
        var result: [SoundCloudTrack] = []
        var next: String? = initialPath

        while let pageURL = next, result.count < maximumItems {
            let page: SoundCloudCollectionPage<SoundCloudTrack> = try await apiGET(
                absoluteOrRelative: pageURL,
                accessToken: accessToken
            )
            result.append(contentsOf: page.collection)
            next = page.nextHref
            if page.collection.isEmpty { break }
        }
        return Array(result.prefix(maximumItems))
    }

    private func fetchAllPlaylists(
        initialPath: String,
        accessToken: String,
        maximumItems: Int
    ) async throws -> [SoundCloudPlaylist] {
        var result: [SoundCloudPlaylist] = []
        var next: String? = initialPath

        while let pageURL = next, result.count < maximumItems {
            let page: SoundCloudCollectionPage<SoundCloudPlaylist> = try await apiGET(
                absoluteOrRelative: pageURL,
                accessToken: accessToken
            )
            result.append(contentsOf: page.collection)
            next = page.nextHref
            if page.collection.isEmpty { break }
        }
        return Array(result.prefix(maximumItems))
    }

    private func apiGET<T: Decodable>(absoluteOrRelative: String, accessToken: String) async throws -> T {
        let url: URL
        if let absolute = URL(string: absoluteOrRelative), absolute.scheme != nil {
            url = absolute
        } else {
            guard let relative = URL(
                string: absoluteOrRelative,
                relativeTo: URL(string: "https://api.soundcloud.com")!
            )?.absoluteURL else {
                throw APIError.badResponse
            }
            url = relative
        }

        try requireTrustedSoundCloudAPIURL(url)

        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("OAuth \(accessToken)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Accept")

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw APIError.badResponse }
        guard (200..<300).contains(http.statusCode) else {
            let message = String(data: data, encoding: .utf8) ?? "Unknown error"
            throw APIError.http(http.statusCode, message)
        }
        return try JSONDecoder().decode(T.self, from: data)
    }

    private func requireTrustedSoundCloudAPIURL(_ url: URL) throws {
        guard url.scheme?.lowercased() == "https",
              url.host?.lowercased() == "api.soundcloud.com" else {
            throw APIError.untrustedTokenDestination
        }
    }
}
