import { getCommitDocsHeaderAndDescription } from '@/utils/defaults'
import  DocsDoodle  from '../../../assets/Docs.svg'

const HeroSection = () => {

    const { header, description, image } = getCommitDocsHeaderAndDescription()

    const defaultHeader = `Boring docs? Not on our watch!`
    const defaultDescription = `Meet Commit Docs, built with Frappe Framework. It is a modern standard for public-facing documentation: beautiful out of the box, easy to maintain, and open source.`
    return (
        <div className="flex flex-col md:flex-row min-h-[50vh] md:h-[50vh] items-center justify-start px-4 sm:px-6 lg:px-6 ">
            <div className="w-full md:w-1/2 p-4 md:p-8 text-center md:text-left">
                <div className="text-3xl sm:text-4xl md:text-5xl lg:text-6xl font-bold font-title_font tracking-tighter mb-6">
                    {header || defaultHeader}
                </div>
                <div className="font-title_font tracking-tight text-base sm:text-lg md:text-xl mb-8">
                    {description || defaultDescription}
                </div>
            </div>
            <div className="w-full md:w-1/2 p-4 md:p-8">
                    <img
                    src={image ? image : DocsDoodle}
                        alt="ManDoodle."
                        className="w-full h-auto max-h-96 md:max-h-[250px] sm:max-h-[200px] lg:max-h-[300px]
                        object-contain"
                />
            </div>
        </div>
    )
}

export default HeroSection
