#!/usr/bin/perl

# by Jared Roach
# created 10/28/25 v0.01 
# modified 

# usage NCATS_Translator_make_test_assets_from_KEGG.pl

#DESCRIPTION
#
#takes text format KEGG pathways and makes pathfinder test assets
#takes each KEGG pathway
#identifies start and end point (if not these are not clear, skip the test)
#picks a random intermediate node (either a compound or an enzyme)
#requires a path between the start and end going through that node

#TODO 
#could require the path to go through ALL (or some subset >1) compounds and enzymes in the path
#could use other pathway sources than KEGG (e..g, molecular biology)
#could constrain the path length (to =, >, or < than the actual pathlength in KEGG)
#relationship of KEGG path length to Translator path length is unclear, as in KEGG, each hop is from a compound to the next, and enzymes don't count as hops (they are equivalent to 1-hop branches in Translator)
#could look for paths between intermediate nodes (rather than start and end)



use warnings FATAL => 'all';  #like to trap all warnings when running in workflow environment becuase otherwise it is easy to miss the warning
#use Scalar::Util qw(looks_like_number);
use List::Util qw(shuffle); 
my $VERSION = '0.02';
my $program = $0;
my $system = `hostname`;
chomp $system;  #e.g., "host.systemsbiology.net"

my $command = "date  +\%m-\%d-\%y";
our $today_date = `$command`;
$today_date =~ s/^0//; #no leading zero on month
$today_date =~ s/-0/-/; #no leading zeros on day
$today_date =~ s/-/_/g; #underscores rather than dashes
chomp $today_date;
print STDERR "Version $VERSION of $program running on $system, with today's date as $today_date.\n";

our $output_directory;
$output_directory = "/Users/jroach/KEGG_pathfinder_test_assets/";
my $input_directory;
$input_directory = "/Users/jroach/KEGG_pathways_for_pathfinder_analysis/";

opendir DIR, $input_directory or die "Cannot open directory: $!";
my @KEGG_files = readdir DIR;
closedir DIR;
my $number_of_KEGG_files = 0;
foreach my $file (sort @KEGG_files) {
	next if ($file =~ /^\./);  #skip invisible files
	#print "\t",$file,"\n";
	if ($file =~ /^M(\d*).txt/) {   #e.g., M00004.txt
		my $var = $1;
		#$seen_KEGG_pathway{$var} = 1;
		#print STDERR "\t\t$var\n";
		make_pathfinder_test_asset($input_directory.$file,$var);
		$number_of_KEGG_files++;
	} else {
		die;
	}
}


print "I parsed $number_of_KEGG_files KEGG pathways.\nThanks so much for running this Translator script --->  :)  Your friendly CATARX Team.\n";

exit;
#END MAIN BLOCK

sub make_pathfinder_test_asset {
	use strict;
	my $subroutine = (caller(0))[3];
	my $filename = shift;
	my $var = shift;
	
	my $pathway_name = "ERROR";
	our %compound_name;
	my @compounds = ();
	open(my $fh, '<', $filename) or die "Could not open file '$filename' $!";
	my $in_compound = 0;
	while (my $line = <$fh>) {
		chomp $line;
		
		if ($line =~ /^NAME\s+(\S.*)/) {
			$pathway_name  = $1;
		}
		
		# Detect the start of the COMPOUND section
		if ($line =~ /^COMPOUND\s+/) {
			$in_compound = 1;
			$line =~ s/^COMPOUND\s+//;
		} elsif ($in_compound && $line =~ /^\S/) {
			# Non-indented, non-empty line means start of a new KEGG section
			last;
		}
		if ($in_compound) {
			# Combine continuation lines (start with whitespace)
			if ($line =~ /^\s*(C\d{5})\s+(.*)/) {
				# Typical compound line
				my $KEGG_compound_ID = $1;
				$compound_name{$KEGG_compound_ID} = $2;
				push @compounds,$KEGG_compound_ID;
			}
		}
	}
	close $fh;
   
  #print STDERR join(", ",@compounds),"\n";
  if (scalar @compounds > 2) {  #if focusing only on compunds (and not enzymes) need path length to be at least two hops in order to have a testable intermediate
  	make_asset(\@compounds,$var,$pathway_name);
  } else {
  	print STDERR "Skipping M$var because it has less than 3 compounds.\n";
  }
  
	#my $b = scalar @data_header;
	#print STDERR "I finished parsing $filename and creating a test asset.\n";

}
#end make_pathfinder_test_asset 


sub make_asset {
	use strict;
	my $subroutine = (caller(0))[3];
	my $compounds = shift;
	my $var = shift;
	my $pathway_name = shift;
	my @compounds = @$compounds;
	our %compound_name;
	
	print STDERR join(", ",@compounds),"\n";
	

my $json_template = <<'END_TEMPLATE';
{
    "id": "{asset_id}",
    "name": "{asset_name}",
    "description": "{asset_description}",
    "tags": [],
    "test_runner_settings": [
        "pathfinder"
    ],
    "source_input_id": "{source_ID}",
    "source_input_name": "{source_name}",
    "source_input_category": "{source_category}",
    "target_input_id": "{target_ID}",
    "target_input_name": "{target_name}",
    "target_input_category": "{target_category}",
    "predicate_id": "biolink:related_to",
    "predicate_name": "related to",
    "minimum_required_path_nodes": 1,
    "path_nodes": [
        {
            "ids": ["{intermediate_ID}"],
            "name": "{intermediate_name}"
        }
    ],
    "association": null,
    "qualifiers": null,
    "expected_output": "TopAnswer",
    "test_issue": null,
    "semantic_severity": null,
    "in_v1": null,
    "well_known": true,
    "test_reference": null,
    "test_metadata": {
        "id": "1",
        "name": null,
        "description": null,
        "tags": [],
        "test_runner_settings": [],
        "test_source": "{provenance}",
        "test_reference": null,
        "test_objective": "AcceptanceTest",
        "test_annotations": []
    }
}
END_TEMPLATE
	
	our $output_directory;
	our $today_date;
	
	my $outfile;  #e.g., Asset_7.json
	my $outfile_root = "Asset_";
	$outfile = $output_directory.$outfile_root."M".$var.".json";
	
	my $asset_id = "Asset_M".$var."_".$today_date;
	my $asset_name = $pathway_name;
	
	my $asset_description = "This is the start and end compound from KEGG pathway M$var, with a random compound from the pathway required to be an intermediate.";
	#my $asset_description = "This iscompound from the pathway required to be an intermediate.";
	
	my $source = $compounds[0];
	my $source_ID = "KEGG.COMPOUND:".$source;
	my $source_name = $compound_name{$source};
	my $source_category = "biolink:ChemicalEntity";
	
	my $target = $compounds[-1];
	my $target_ID = "KEGG.COMPOUND:".$target;
	my $target_name = $compound_name{$target};
	my $target_category = "biolink:ChemicalEntity";
	
	#pick a random intermdiate
	my @intermediates = @compounds;
	shift @intermediates; #get rid of source
	pop @intermediates;  #get rid of target
	@intermediates =  shuffle(@intermediates); 
	my $intermediate = pop @intermediates;
	
	my $intermediate_ID = "KEGG.COMPOUND:".$intermediate;
	my $intermediate_name = $compound_name{$intermediate};
	#my $intermediate_category = "biolink:ChemicalEntity";
	
	my %values = (
    asset_id => $asset_id,
    asset_name => $asset_name,
    asset_description => $asset_description,
    source_ID => $source_ID,
    source_name => $source_name,
    source_category => $source_category,
    target_ID => $target_ID,
    target_name => $target_name,
    target_category => $target_category,
    intermediate_ID => $intermediate_ID,
    intermediate_name => $intermediate_name,
    provenance => "NCATS_Translator_make_test_assets_from_KEGG.pl"
    );
  
  my $filled = fill_template($json_template, \%values);
  
	open(OUT,">$outfile");
	print OUT $filled;
	close OUT;
	
	
}
#end make_asset


sub fill_template {
    my ($template, $vars) = @_;
    # Replace placeholders like {variable} with values from %$vars
    $template =~ s/\{(\w+)\}/
        exists $vars->{$1} ? $vars->{$1} : "{$1}"
    /ge;
    return $template;
}