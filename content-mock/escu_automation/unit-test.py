from unittest import mock, TestCase

class ESCUBaselineCreator(TestCase):
    
    def test_snake_case(self):
        '''
        # Test snake_case function:
        This test checks the `snake_case` function, which transforms a string into snake case format.
        Expected to convert spaces and special characters into underscores, and lowercase the string.
        '''
        mock_string = "Test String"
        new_string = escu_baseline_creator.snake_case(mock_string)
        assert new_string == "test_string"
    
    def test_validate_mitre_id(self):
        '''
        # Test validate_mitre_id function:
        This test checks if the MITRE ID validation is working as expected.
        Valid MITRE IDs are of the form T1234 or T1234.001, and invalid IDs should return False.
        '''
        assert escu_baseline_creator.validate_mitre_id("T1234") == True
        assert escu_baseline_creator.validate_mitre_id("T1234.001") == True
        assert escu_baseline_creator.validate_mitre_id("INVALID1234") == False

    @mock.patch('os.path.join')
    @mock.patch('os.makedirs')
    @mock.patch('builtins.open')
    def test_create_macro_file(self, mock_open, mock_os_makedirs, mock_os_join):
        '''
        # Test create_macro_file function:
        This test ensures that the function creates directories and files as expected.
        We're mocking file system interactions to avoid actual file creation.
        '''
        mock_os_join.return_value = "test_path"
        
        escu_baseline_creator.create_macro_file("macro_name", "macro_dir")
        
        assert mock_os_makedirs.called
        assert mock_os_join.called
        assert mock_open.called

    @mock.patch('os.walk')
    def test_load_detections(self, mock_os_walk):
        '''
        # Test load_detections function:
        This function searches through detection YAML files to find matching MITRE IDs.
        We mock `os.walk` to simulate a directory structure, and we load dummy YAML content for testing.
        '''
        # Mock directory structure and files
        mock_os_walk.return_value = [
            ('detections/application', ('subdir',), ('file1.yml',)),
            ('detections/application/subdir', (), ('file2.yml',))
        ]

        # Mock file content
        mock_file_content = """
        tags:
          mitre_attack_id: ['T1234']
        """
        with mock.patch('builtins.open', mock.mock_open(read_data=mock_file_content)):
            detections = escu_baseline_creator.load_detections('fake_repo_path', 'T1234')
            assert len(detections) == 1  # We expect 1 detection to be found

    @mock.patch('os.path.join')
    @mock.patch('os.makedirs')
    @mock.patch('builtins.open')
    def test_create_correlation_search_file(self, mock_open, mock_os_makedirs, mock_os_join):
        '''
        # Test create_correlation_search_file function:
        This test verifies that correlation search YAML files are created with proper content.
        We'll mock file operations and ensure the expected data structure is written to the file.
        '''
        escu_baseline_creator.create_correlation_search_file(
            escu_id="test_escu_id",
            title="Test Correlation Search",
            splunk_escu_id="splunk_escu_1234",
            description="Test Description",
            mitre_attack_ids=["T1234"],
            tuning_macros=["macro1", "macro2"],
            content="search SPL",
            required_fields=["field1", "field2"],
            output_dir="test_output_dir"
        )
        
        assert mock_open.called  # Check if the file was opened
        # Check if the content is written to the file correctly
        mock_open().write.assert_any_call("id: test_escu_id\n")
        mock_open().write.assert_any_call("splunk_escu_id: splunk_escu_1234\n")

    def test_expand_macros_in_spl(self):
        '''
        # Test expand_macros_in_spl function:
        This function replaces macros in the SPL content with their full definitions.
        We pass in a mock SPL string and mock macro definitions to test the function's behavior.
        '''
        spl_content = "`macro1` | search field=value"
        macro_definitions = {"macro1": "expanded_macro1"}
        
        expanded_spl = escu_baseline_creator.expand_macros_in_spl(spl_content, macro_definitions, escu_baseline_creator.EXCLUDED_MACROS)
        
        # Check if the macro was expanded
        assert expanded_spl == "(expanded_macro1) | search field=value"
    
    def test_should_exclude_detection(self):
        '''
        # Test should_exclude_detection function:
        This test checks whether a detection is excluded based on its search content.
        Specifically, detections that do not contain "| tstats" should be excluded.
        '''
        detection = {
            'name': 'Test Detection',
            'search': '| tstats count where index=_internal'
        }
        assert escu_baseline_creator.should_exclude_detection(detection) == False

        detection_no_tstats = {
            'name': 'Detection without tstats',
            'search': 'index=_internal'
        }
        assert escu_baseline_creator.should_exclude_detection(detection_no_tstats) == True

    def test_extract_datamodel_name(self):
        '''
        # Test extract_datamodel_name function:
        This function extracts the datamodel name from a string that contains 'datamodel=<value>'.
        We're testing if the correct datamodel is returned when present, and None when absent.
        '''
        spl_content = "| tstats count from datamodel=Network_Traffic"
        datamodel_name = escu_baseline_creator.extract_datamodel_name(spl_content)
        
        # Check if the correct datamodel name is extracted
        assert datamodel_name == "Network_Traffic"
        
        # Test with no datamodel present
        spl_content_no_datamodel = "| tstats count"
        datamodel_name = escu_baseline_creator.extract_datamodel_name(spl_content_no_datamodel)
        assert datamodel_name == None

    @mock.patch('os.walk')
    def test_load_macro_definitions(self, mock_os_walk):
        '''
        # Test load_macro_definitions function:
        This function loads macro definitions from YAML files. We mock `os.walk` to simulate a directory structure
        and mock file content to test the function's behavior.
        '''
        # Mock directory structure
        mock_os_walk.return_value = [
            ('macros', (), ('macro1.yml',)),
        ]

        # Mock file content
        mock_file_content = """
        name: macro1
        definition: search index=*
        """
        with mock.patch('builtins.open', mock.mock_open(read_data=mock_file_content)):
            macro_definitions = escu_baseline_creator.load_macro_definitions('fake_macro_dir')
            assert 'macro1' in macro_definitions
            assert macro_definitions['macro1'] == "search index=*"
    
    def test_process_filters_in_spl(self):
        '''
        # Test process_filters_in_spl function:
        This test checks if filters in the SPL are correctly processed and expanded.
        We simulate a SPL content and mock macro definitions to verify the behavior.
        '''
        spl_content = "| search field=value | `nh-aw_escu_test_input_filter` | `nh-aw_escu_test_filter`"
        detection_id = "nh-aw_escu_test"
        macro_definitions = {}
        
        processed_spl = escu_baseline_creator.process_filters_in_spl(spl_content, detection_id, macro_definitions)
        
        # Verify if input and output filters are appended correctly
        assert "| `nh-aw_escu_test_input_filter`" in processed_spl
        assert "| `nh-aw_escu_test_output_filter`" in processed_spl