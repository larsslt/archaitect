// Local OCR of one PDF page. No network, shell, or PDF actions are executed.
import Foundation
import PDFKit
import Vision
import AppKit
let args=CommandLine.arguments
if args.count != 3 {exit(2)}
guard let doc=PDFDocument(url:URL(fileURLWithPath:args[1])), let number=Int(args[2]), let page=doc.page(at:number-1) else {exit(3)}
let bounds=page.bounds(for:.mediaBox)
let scale=min(2.5,9000/max(bounds.width,bounds.height))
let width=Int(bounds.width*scale), height=Int(bounds.height*scale)
let side=1800, overlap=80
var failures=0
for top in stride(from:0,to:height,by:side-overlap) {
    for left in stride(from:0,to:width,by:side-overlap) {
        autoreleasepool {
            let w=min(side,width-left),h=min(side,height-top)
            guard let ctx=CGContext(data:nil,width:w,height:h,bitsPerComponent:8,bytesPerRow:w*4,space:CGColorSpaceCreateDeviceRGB(),bitmapInfo:CGImageAlphaInfo.noneSkipLast.rawValue) else {return}
            ctx.setFillColor(CGColor(gray:1,alpha:1));ctx.fill(CGRect(x:0,y:0,width:w,height:h))
            ctx.translateBy(x:-CGFloat(left),y:CGFloat(h-height+top));ctx.scaleBy(x:scale,y:scale)
            ctx.translateBy(x:-bounds.minX,y:-bounds.minY);page.draw(with:.mediaBox,to:ctx)
            guard let image=ctx.makeImage() else {return}
            let request=VNRecognizeTextRequest();request.recognitionLevel = .accurate
            request.recognitionLanguages=["de-DE","en-US"];request.usesLanguageCorrection=true
            do {
                try VNImageRequestHandler(cgImage:image).perform([request])
                for line in request.results ?? [] {if let text=line.topCandidates(1).first {print(text.string)}}
            } catch {failures += 1; fputs("OCR tile failed\n",stderr)}
        }
    }
}

if failures > 0 {exit(4)}
