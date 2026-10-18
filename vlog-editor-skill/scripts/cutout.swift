// Subject cut-out with Apple Vision (same tech as iPhone "lift subject") -- on-device, nothing uploaded.
// build once:  swiftc -O cutout.swift -o cutout        (macOS 14+)
// use:         ./cutout frame.png subject.png            -> RGBA PNG, background transparent
import CoreImage
import Foundation
import ImageIO
import UniformTypeIdentifiers
import Vision

let args = CommandLine.arguments
guard args.count == 3 else { print("usage: cutout in.png out.png"); exit(2) }
guard let src = CGImageSourceCreateWithURL(URL(fileURLWithPath: args[1]) as CFURL, nil),
      let cg = CGImageSourceCreateImageAtIndex(src, 0, nil) else { fatalError("cannot read \(args[1])") }
let req = VNGenerateForegroundInstanceMaskRequest()
let handler = VNImageRequestHandler(cgImage: cg, options: [:])
try handler.perform([req])
guard let obs = req.results?.first else { fatalError("no subject found") }
let buf = try obs.generateMaskedImage(ofInstances: obs.allInstances, from: handler, croppedToInstancesExtent: false)
let ci = CIImage(cvPixelBuffer: buf)
guard let out = CIContext().createCGImage(ci, from: ci.extent) else { fatalError("render failed") }
let dest = CGImageDestinationCreateWithURL(URL(fileURLWithPath: args[2]) as CFURL, UTType.png.identifier as CFString, 1, nil)!
CGImageDestinationAddImage(dest, out, nil)
CGImageDestinationFinalize(dest)
print("subjects:", obs.allInstances.count)
