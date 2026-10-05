// ocr.swift: read the words in a picture with macOS Vision and print them as JSON, one entry per line of text:
// {"t": text, "x": centre x, "y": centre y, "w": width, "h": height} in picture pixels, top-left origin.
// Build once: swiftc -O scripts/ocr.swift -o .gdt/ocr    Use: .gdt/ocr shot.png
import AppKit
import Vision

guard CommandLine.arguments.count > 1, let img = NSImage(contentsOfFile: CommandLine.arguments[1]),
      let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { FileHandle.standardError.write("usage: ocr picture.png\n".data(using: .utf8)!); exit(1) }
let W = Double(cg.width), H = Double(cg.height)
let req = VNRecognizeTextRequest()
req.recognitionLevel = .accurate
req.usesLanguageCorrection = false
try VNImageRequestHandler(cgImage: cg).perform([req])
var out: [[String: Any]] = []
for o in req.results ?? [] {
    guard let c = o.topCandidates(1).first else { continue }
    let b = o.boundingBox
    out.append(["t": c.string, "x": Int(b.midX * W), "y": Int((1 - b.midY) * H), "w": Int(b.width * W), "h": Int(b.height * H)])
}
print(String(data: try JSONSerialization.data(withJSONObject: out), encoding: .utf8)!)
