class Backeer < Formula
  include Language::Python::Virtualenv

  desc "YouTube audio to Audacity stems — downloads, separates with Demucs, opens in Audacity"
  homepage "https://github.com/architgosain/Backeer"
  head "https://github.com/architgosain/Backeer.git", branch: "main"

  depends_on "python@3.13"
  depends_on "yt-dlp"
  depends_on "ffmpeg"

  def install
    virtualenv_install_with_resources
  end

  def post_install
    opoo "Backeer needs demucs and torchcodec. Install them into the formula venv:"
    puts "  #{libexec}/bin/pip install demucs torchcodec"
  end

  def caveats
    <<~EOS
      Available models: htdemucs_6s (6 stems), htdemucs (4 stems),
      htdemucs_ft (4 stems, fine-tuned), mdx_extra (4 stems).

      Create a backeer.toml to set defaults:

        [backeer]
        model = "htdemucs_6s"
        runs-dir = "~/backeer-runs"
        with-audacity = true
    EOS
  end

  test do
    system bin/"backeer", "--help"
  end
end
